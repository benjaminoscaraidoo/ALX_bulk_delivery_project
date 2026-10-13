(() => {
  const message = (form, text, error = false) => {
    const el = form.querySelector('.form-message');
    el.textContent = text; el.classList.toggle('error', error);
  };
  const errors = value => {
    if (Array.isArray(value)) return value.map(errors).join(' ');
    if (value && typeof value === 'object') return Object.entries(value).map(([key, val]) => `${key === 'detail' || key === 'non_field_errors' ? '' : key + ': '}${errors(val)}`).join(' ');
    return String(value);
  };
  const send = async (form, url, data, method = 'POST') => {
    const response = await fetch(url, {method, credentials: 'same-origin', headers: {'Content-Type':'application/json', 'X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value}, body:JSON.stringify(data)});
    const body = await response.json().catch(() => ({detail:'The server could not complete this request. Please try again.'}));
    if (!response.ok) throw new Error(errors(body));
    return body;
  };
  document.querySelectorAll('[data-area-toggle]').forEach(input => {
    input.addEventListener('change', () => {
      const field = input.form.querySelector('[data-area-field]');
      field.hidden = !input.checked; field.querySelector('select').required = input.checked;
      if (!input.checked) field.querySelector('select').value = '';
    });
  });
  document.querySelectorAll('form[data-account="register"]').forEach(form => {
    const role = form.querySelector('[name=role]');
    const channel = form.querySelector('[name=delivery_channel]');
    const update = () => {
      if (role.value === 'driver') channel.value = 'sms';
      channel.querySelector('[value=email]').disabled = role.value === 'driver';
      const sms = channel.value === 'sms';
      form.querySelector('[name=phone_number]').required = sms;
      form.querySelector('[name=email]').required = !sms;
      form.querySelector('[data-phone-note]').textContent = sms ? '(required)' : '(optional until your first order)';
      form.querySelector('[data-email-note]').textContent = sms ? '(optional; verify later)' : '(required)';
    };
    role.addEventListener('change', update); channel.addEventListener('change', update); update();
  });
  document.querySelectorAll('form[data-contact]').forEach(form => {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button'); button.disabled = true;
      try {
        const data = Object.fromEntries(new FormData(form)); delete data.csrfmiddlewaretoken;
        if (form.dataset.contactStage === 'verify') {
          await send(form, '/api/v1/account/contact/verify/', {delivery_channel: data.delivery_channel, otp: data.otp});
          window.location.reload();
        } else {
          await send(form, '/api/v1/account/contact/request/', {delivery_channel: data.delivery_channel, value: data.value});
          form.dataset.contactStage = 'verify';
          const otp = form.querySelector('[name=otp]'); otp.disabled = false; otp.required = true; otp.closest('label').hidden = false;
          form.querySelector('[name=value]').readOnly = true;
          button.textContent = 'Verify contact';
          message(form, 'Code sent. Enter it below.');
        }
      } catch (error) {message(form, error.message, true);}
      finally {button.disabled = false;}
    });
  });
  document.querySelectorAll('form[data-api], form[data-account]').forEach(form => {
    let stage = 'request';
    const showVerification = (identifier, channel) => {
      stage = 'verify';
      form.dataset.identifier = identifier; form.dataset.channel = channel;
      form.querySelector('[data-request-step]').hidden = true;
      form.querySelector('[data-request-step]').querySelectorAll('input, select').forEach(el => el.disabled = true);
      form.querySelector('[data-verify-step]').hidden = false;
      form.querySelector('[data-verify-step]').querySelectorAll('input').forEach(el => {el.disabled = false; el.required = true;});
      form._confirmationToken = null;
      message(form, 'Code sent. Check your selected email or phone.');
      form.querySelector('[name=otp]').focus();
    };
    form.querySelector('[data-resend]')?.addEventListener('click', async () => {
      const button = form.querySelector('[data-resend]');
      button.disabled = true;
      try {
        const identifier = form.dataset.account === "register" ? (form.querySelector("[name=delivery_channel]").value === "sms" ? form.querySelector("[name=phone_number]").value : form.querySelector("[name=email]").value) : form.querySelector("[name=identifier]").value;
        const channel = form.querySelector('[name=delivery_channel]').value;
        const kind = form.dataset.account;
        const payload = {identifier, delivery_channel:channel};
        if (kind === 'register') payload.password = form.querySelector('[name=password]').value;
        await send(form, kind === 'register' ? '/api/v1/register/resend/' : '/api/v1/password-reset/request/', payload);
        showVerification(identifier, channel);
      } catch (error) {message(form, error.message, true);}
      finally {button.disabled = false;}
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (event.submitter?.dataset.confirm && !window.confirm(event.submitter.dataset.confirm)) return;
      const buttons = [...form.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
      message(form, 'Working…');
      try {
        const data = Object.fromEntries(new FormData(form)); delete data.csrfmiddlewaretoken;
        for (const input of form.querySelectorAll('input[type=checkbox]')) data[input.name] = input.checked;
        if ('delivery_area' in data && !data.delivery_area) delete data.delivery_area;
        if (form.dataset.account) {
          const kind = form.dataset.account;
          if (stage === 'request') {
            if (!data.email) delete data.email;
            if (!data.phone_number) delete data.phone_number;
            const payload = kind === 'register' ? data : {identifier:data.identifier, delivery_channel:data.delivery_channel};
            await send(form, `/api/v1/${kind}/request/`, payload);
            showVerification(kind === "register" ? (data.delivery_channel === "sms" ? data.phone_number : data.email) : data.identifier, data.delivery_channel);
          } else {
            // Retain a verified token in memory if confirmation needs a corrected password.
            let token = form._confirmationToken;
            if (!token) {
              const verified = await send(form, `/api/v1/${kind}/verify/`, {identifier:form.dataset.identifier, otp:data.otp, delivery_channel:form.dataset.channel});
              token = verified[kind === 'register' ? 'register_token' : 'reset_token'];
              form._confirmationToken = token;
            }
            const payload = kind === 'register' ? {identifier:form.dataset.identifier, register_token:token} : {reset_token:token, new_password:data.new_password};
            await send(form, `/api/v1/${kind}/confirm/`, payload);
            window.location.assign('/login/');
          }
        } else {
          let payload = data;
          if (form.dataset.mode === 'package') {const {order_id, ...parcel} = data; payload = {order_id, packages:[parcel]};}
          if (form.dataset.mode === 'delivery') payload = {deliveries:[data]};
          const result = await send(form, form.dataset.api, payload, form.dataset.method || 'POST');
          if (result.quote_required) {message(form, 'This delivery needs an administrator quote. Please contact support.'); return;}
          if (form.dataset.mode === 'order') window.location.assign(`/orders/${encodeURIComponent(result.id)}/`);
          else window.location.reload();
        }
      } catch (error) {message(form, error.message || 'Unable to connect. Please try again.', true);}
      finally {buttons.forEach(b => b.disabled = false);}
    });
  });
})();
