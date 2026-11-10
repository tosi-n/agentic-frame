"""Client for HybrIE's resident, scoped audio and video generation jobs.

This is an operator transport. It requires a HybrIE bearer key and the exact
business profile/pool scope of a ready resident deployment. It is not the
Console public inference API.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

Family = Literal["audio", "video"]
TERMINAL = frozenset({"succeeded", "failed", "cancelled"})


class MediaError(RuntimeError):
    """A scoped media request failed or returned an unexpected response."""


class MediaClient:
    def __init__(
        self,
        base_url: str,
        bearer_key: str,
        business_profile_id: str,
        pool_id: str,
        project_id: str | None = None,
        *,
        timeout: float = 30,
    ) -> None:
        if not base_url.startswith("https://") and not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("HybrIE must use HTTPS or a loopback URL")
        if not bearer_key:
            raise ValueError("HybrIE bearer key is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {bearer_key}",
            "X-Hybrie-Business-Profile-Id": str(UUID(business_profile_id)),
            "X-Hybrie-Pool-Id": str(UUID(pool_id)),
        }
        if project_id:
            self.headers["X-Hybrie-Project-Id"] = str(UUID(project_id))

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None = None,
                 deployment_id: str | None = None, family: Family | None = None) -> bytes:
        headers = dict(self.headers)
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        if deployment_id and family:
            headers[f"X-Hybrie-{family.title()}-Deployment-Id"] = deployment_id
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read(1024).decode("utf-8", errors="replace")
            raise MediaError(f"HybrIE HTTP {exc.code}: {detail}") from exc

    def deployments(self, family: Family) -> list[dict[str, Any]]:
        result = json.loads(self._request("GET", f"/v1/compute/{family}/deployments"))
        return result["deployments"]

    def submit(self, family: Family, deployment: dict[str, Any], request: dict[str, Any],
               *, job_id: str) -> dict[str, Any]:
        if deployment.get("ready") is not True:
            raise ValueError("Deployment is not ready")
        job_id = str(UUID(job_id))
        body = {
            **request,
            "model": deployment["model"],
            "deployment_id": deployment["deployment_id"],
            "model_fingerprint": deployment["model_fingerprint"],
            "deployment_revision": deployment["deployment_revision"],
        }
        return json.loads(self._request("PUT", f"/v1/compute/{family}/jobs/{job_id}", body=body))

    def status(self, family: Family, job_id: str, deployment_id: str) -> dict[str, Any]:
        job_id = str(UUID(job_id))
        return json.loads(self._request("GET", f"/v1/compute/{family}/jobs/{job_id}",
                                        deployment_id=deployment_id, family=family))

    def wait(self, family: Family, job_id: str, deployment_id: str, *,
             timeout: float = 3600, interval: float = 2) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            result = self.status(family, job_id, deployment_id)
            if result["state"] in TERMINAL:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"HybrIE {family} job {job_id} is still {result['state']}")
            time.sleep(min(interval, remaining))

    def artifact(self, family: Family, job_id: str, deployment_id: str, destination: Path) -> Path:
        job_id = str(UUID(job_id))
        expected = ".wav" if family == "audio" else ".mp4"
        if destination.suffix.lower() != expected:
            raise ValueError(f"{family} artifact destination must end in {expected}")
        headers = dict(self.headers)
        headers[f"X-Hybrie-{family.title()}-Deployment-Id"] = deployment_id
        source = Request(
            f"{self.base_url}/v1/compute/{family}/jobs/{job_id}/artifact",
            headers=headers,
            method="GET",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with urlopen(source, timeout=self.timeout) as response:
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as out:
                    temporary = Path(out.name)
                    while chunk := response.read(1024 * 1024):
                        out.write(chunk)
            os.replace(temporary, destination)
        except HTTPError as exc:
            detail = exc.read(1024).decode("utf-8", errors="replace")
            raise MediaError(f"HybrIE HTTP {exc.code}: {detail}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return destination
