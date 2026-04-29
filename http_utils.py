import requests


def raise_for_status(response: requests.Response, service: str) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        detail = response.text[:500]
        raise RuntimeError(
            f"{service} request failed with {response.status_code}: {detail}"
        ) from error
