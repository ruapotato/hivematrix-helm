"""
URL Prefix Middleware for HiveMatrix Services

This middleware adjusts the WSGI environment to handle URL prefixes
when the service is running behind the Nexus reverse proxy.
"""

class PrefixMiddleware:
    """
    Middleware to handle URL prefix when behind a reverse proxy (Nexus).

    When a service is accessed through Nexus at /helm/*, this middleware
    ensures Flask routes work correctly by adjusting SCRIPT_NAME and PATH_INFO.
    """

    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix.rstrip('/')

    def __call__(self, environ, start_response):
        if self.prefix:
            # Adjust SCRIPT_NAME and PATH_INFO for the prefix
            script_name = environ.get('SCRIPT_NAME', '')
            path_info = environ.get('PATH_INFO', '')

            if path_info.startswith(self.prefix):
                environ['SCRIPT_NAME'] = script_name + self.prefix
                environ['PATH_INFO'] = path_info[len(self.prefix):]

        return self.app(environ, start_response)
