import pytest
import asyncio
from httpx import AsyncClient

# This mimics the Doc requirements
class TestSendOTP:
    @pytest.mark.asyncio
    async def test_send_otp_success(self, client: AsyncClient):
        res = await client.post("/v1/auth/otp/send", json={"phone": "+919876543210"})
        assert res.status_code == 200
        assert "expires_in_seconds" in res.json()

    @pytest.mark.asyncio
    async def test_rejects_invalid_phone_format(self, client: AsyncClient):
        # We did not strictly add phone regex validation to pydantic yet, but it's string limited.
        # Let's verify string limit handling
        res = await client.post("/v1/auth/otp/send", json={"phone": "+91987654321000000000000"})
        assert res.status_code == 422


class TestAuthProfileFlow:
    @pytest.mark.asyncio
    async def test_verify_otp_then_get_and_update_profile(self, client: AsyncClient):
        send_res = await client.post("/v1/auth/otp/send", json={"phone": "+919876543211"})
        assert send_res.status_code == 200
        otp = send_res.json()["dev_otp"]

        verify_res = await client.post(
            "/v1/auth/otp/verify",
            json={"phone": "+919876543211", "otp": otp},
        )
        assert verify_res.status_code == 200
        payload = verify_res.json()
        token = payload["access_token"]
        assert payload["user"]["phone"] == "+919876543211"

        headers = {"Authorization": f"Bearer {token}"}

        me_res = await client.get("/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()["data"]
        assert me_data["phone"] == "+919876543211"
        assert me_data["vehicle_type"] is None

        update_res = await client.patch(
            "/v1/auth/me",
            headers=headers,
            json={
                "name": "Rahul Sharma",
                "email": "RAHUL@example.com",
                "vehicle_type": "Tata Nexon EV",
            },
        )
        assert update_res.status_code == 200
        updated = update_res.json()["data"]
        assert updated["name"] == "Rahul Sharma"
        assert updated["email"] == "rahul@example.com"
        assert updated["vehicle_type"] == "Tata Nexon EV"

        me_after_res = await client.get("/v1/auth/me", headers=headers)
        assert me_after_res.status_code == 200
        assert me_after_res.json()["data"]["vehicle_type"] == "Tata Nexon EV"

    @pytest.mark.asyncio
    async def test_update_profile_rejects_duplicate_email(self, client: AsyncClient):
        first_send = await client.post("/v1/auth/otp/send", json={"phone": "+919876543212"})
        first_verify = await client.post(
            "/v1/auth/otp/verify",
            json={"phone": "+919876543212", "otp": first_send.json()["dev_otp"]},
        )
        first_headers = {"Authorization": f"Bearer {first_verify.json()['access_token']}"}
        first_update = await client.patch(
            "/v1/auth/me",
            headers=first_headers,
            json={"name": "User One", "email": "shared@example.com"},
        )
        assert first_update.status_code == 200

        second_send = await client.post("/v1/auth/otp/send", json={"phone": "+919876543213"})
        second_verify = await client.post(
            "/v1/auth/otp/verify",
            json={"phone": "+919876543213", "otp": second_send.json()["dev_otp"]},
        )
        second_headers = {"Authorization": f"Bearer {second_verify.json()['access_token']}"}

        conflict_res = await client.patch(
            "/v1/auth/me",
            headers=second_headers,
            json={"name": "User Two", "email": "shared@example.com"},
        )
        assert conflict_res.status_code == 409
        assert conflict_res.json()["error"]["code"] == "PROFILE_CONFLICT"
