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
  document.querySelectorAll('form[data-api], form[data-account]').forEach(form => {
    let stage = 'request';
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
            const payload = kind === 'register' ? data : {email:data.email};
            await send(form, `/api/v1/${kind}/request/`, payload);
            stage = 'verify';
            form.querySelector('[data-request-step]').hidden = true;
            form.querySelector('[data-request-step]').querySelectorAll('input, select').forEach(el => el.disabled = true);
            form.querySelector('[data-verify-step]').hidden = false;
            form.querySelector('[data-verify-step]').querySelectorAll('input').forEach(el => {el.disabled = false; el.required = true;});
            form.dataset.email = data.email;
            message(form, 'Code sent. Check your email.');
            form.querySelector('[name=otp]').focus();
          } else {
            // Retain a verified token in memory if confirmation needs a corrected password.
            let token = form._confirmationToken;
            if (!token) {
              const verified = await send(form, `/api/v1/${kind}/verify/`, {email:form.dataset.email, otp:data.otp});
              token = verified[kind === 'register' ? 'register_token' : 'reset_token'];
              form._confirmationToken = token;
            }
            const payload = kind === 'register' ? {email:form.dataset.email, register_token:token} : {reset_token:token, new_password:data.new_password};
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
