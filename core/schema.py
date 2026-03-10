from drf_spectacular.openapi import AutoSchema


class CustomAutoSchema(AutoSchema):

    def get_tags(self):
        """
        Automatically group endpoints by app name
        """
        if self.view.__class__.__module__:
            return [self.view.__class__.__module__.split(".")[0]]

        return super().get_tags()