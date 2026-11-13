from gunicorn.glogging import Logger


class GuruLogger(Logger):
    def atoms(self, resp, req, environ, request_time):
        atoms = super().atoms(resp, req, environ, request_time)
        path = environ.get("PATH_INFO", "")
        if path.startswith("/api/invites/") and path != "/api/invites/":
            atoms["U"] = atoms["r"] = "/api/invites/[redacted]"
            atoms["q"] = ""
        return atoms
