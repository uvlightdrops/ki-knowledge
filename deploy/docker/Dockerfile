# ki-knowledge app image (Django UI + knowledge API, selected by command).
# Built by stackctl: sibling repos arrive as named build contexts
# (--build-context ki-core=… etc.), the main context holds only git-visible files.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=yaml_cfg_wizard . /src/yaml_cfg_wizard
COPY --from=ki-core . /src/ki-core
COPY --from=widgetkit-django . /src/widgetkit-django
RUN pip install /src/yaml_cfg_wizard /src/ki-core /src/widgetkit-django

# third-party dependencies first: cached as long as pyproject.toml is unchanged
WORKDIR /app
COPY pyproject.toml ./
RUN python - <<'PY'
import subprocess, sys, tomllib
deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]
local = {"ki-core", "widgetkit-django", "yaml-cfg-wizard"}
deps = [d for d in deps if not any(d.startswith(name) for name in local)]
subprocess.check_call([sys.executable, "-m", "pip", "install", *deps])
PY

COPY . /app
RUN pip install --no-deps -e /app

EXPOSE 8000 8090
CMD ["python", "manage.py", "runserver", "--insecure", "--noreload", "0.0.0.0:8000"]
