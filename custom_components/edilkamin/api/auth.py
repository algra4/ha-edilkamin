import asyncio
import json
import logging
from datetime import datetime, timedelta

import aiohttp
from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)


class Auth:
    """Class to make authenticated requests."""

    amazon_cognito = "https://cognito-idp.eu-central-1.amazonaws.com/"
    payload = {
        "UserContextData": {
            "EncodedData": "eyJwYXlsb2FkIjoie1widXNlcm5hbWVcIjpcImFkOTVmMzliLWY5ZDEtNDI5Mi04MDgyLWNhNDA1NDZjNzU4ZlwiLFwiY29udGV4dERhdGFcIjp7XCJDYXJyaWVyXCI6XCJPcmFuZ2UgQlwiLFwiQXBwbGljYXRpb25WZXJzaW9uXCI6XCIxLjIuOS03M1wiLFwiSGFzU2ltQ2FyZFwiOlwidHJ1ZVwiLFwiUGhvbmVUeXBlXCI6XCJpUGhvbmUxMiwzXCIsXCJEZXZpY2VJZFwiOlwiYjM1ZjllNTctNDliMS00MzRhLWE0ZDAtOTJhOGMzMWJmNTAyXCIsXCJOZXR3b3JrVHlwZVwiOlwiQ1RSYWRpb0FjY2Vzc1RlY2hub2xvZ3lMVEVcIixcIlNjcmVlbldpZHRoUGl4ZWxzXCI6XCIxMTI1XCIsXCJQbGF0Zm9ybVwiOlwiaU9TXCIsXCJTY3JlZW5IZWlnaHRQaXhlbHNcIjpcIjI0MzZcIixcIkFwcGxpY2F0aW9uVGFyZ2V0U2RrXCI6XCI5MDAwMFwiLFwiQXBwbGljYXRpb25OYW1lXCI6XCJjb20uZWRpbGthbWluLnRoZW1pbmRcIixcIkRldmljZU9zUmVsZWFzZVZlcnNpb25cIjpcIjE1LjQuMVwiLFwiRGV2aWNlRmluZ2VycHJpbnRcIjpcIkFwcGxlXFxcL2lQaG9uZVxcXC9pUGhvbmUxMiwzXFxcLy06MTUuNC4xXFxcLy1cXFwvLTotXFxcL3JlbGVhc2VcIixcIlRoaXJkUGFydHlEZXZpY2VJZFwiOlwiNzY3NjkzNjgtMUZDMS00QjQ5LTk2QjctMkRGMEFEQUQzOTVEXCIsXCJEZXZpY2VMYW5ndWFnZVwiOlwiZnItQkVcIixcIkNsaWVudFRpbWV6b25lXCI6XCIrMDI6MDBcIixcIkJ1aWxkVHlwZVwiOlwicmVsZWFzZVwiLFwiRGV2aWNlTmFtZVwiOlwiSE9NRSBBU1NJU1RBTlRcIn0sXCJ1c2VyUG9vbElkXCI6XCJldS1jZW50cmFsLTFfQlltUTJWQmxvXCIsXCJ0aW1lc3RhbXBcIjpcIjE2NTAyMTQ5OTI5NDZcIn0iLCJ2ZXJzaW9uIjoiSU9TMjAxNzExMTQiLCJzaWduYXR1cmUiOiJCQTU0cTZnZXY4WTFFcmZodUxvaTRja0hBSEcyK1Y1cEZpTU5nNElMVTFZPSJ9"
        },
        "AuthParameters": {"REFRESH_TOKEN": "$REPLACE_BY_INPUT_VALUE$"},
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "ClientId": "$CLIENT_ID$",
    }

    headers = {
        "content-type": "application/x-amz-json-1.1",
        "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
    }

    def __init__(self, websession: ClientSession, refresh_token: str, client_id: str):
        """Initialize the auth."""
        self.access_token = None
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.expires_in = datetime.now()
        self.websession = websession

    async def get_token(self):

        if datetime.now() < self.expires_in:
            _LOGGER.debug(
                "Get access token cached, refrehs token after %s", self.expires_in
            )
            return self.access_token
        try:
            _LOGGER.debug("Set refresh token and client id with provided information")
            self.payload["AuthParameters"]["REFRESH_TOKEN"] = self.refresh_token
            self.payload["ClientId"] = self.client_id
            json_payload = json.dumps(self.payload)

            _LOGGER.debug("Get access token")
            response = await self.websession.request(
                "POST", self.amazon_cognito, headers=self.headers, data=json_payload
            )
            data = await response.text()
            data = json.loads(data)
            _LOGGER.debug(data)
            self.access_token = data.get("AuthenticationResult").get("AccessToken")
            expires_in = data.get("AuthenticationResult").get("ExpiresIn")
            self.expires_in = datetime.now() + timedelta(seconds=expires_in)

            return self.access_token
        except aiohttp.ClientError as error:
            _LOGGER.error("Error connecting to Edilkamin API: %s", error)
        except asyncio.TimeoutError as error:
            _LOGGER.debug("Timeout connecting to Edilkamin API: %s", error)

        return None
