# heygen_api_client.py
import requests
import time
import json
import os
import mimetypes
import logging


class HeyGenAPIClient:
    DEFAULT_V1_BASE_URL = "https://api.heygen.com/v1"
    DEFAULT_V2_BASE_URL = "https://api.heygen.com/v2"
    DEFAULT_UPLOAD_URL = "https://upload.heygen.com/v1"

    def __init__(self, api_key: str, logger=None):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key
        self.logger = logger or self._setup_default_logger()

    def _setup_default_logger(self):
        logger = logging.getLogger(__name__ + ".HeyGenAPIClient")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _log(self, message: str, level: str = "info"):
        if level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "success":
            self.logger.info(f"SUCCESS: {message}")
        else:
            self.logger.info(message)

    def _get_api_url(self, endpoint: str, api_version: str = "v2") -> str:
        base_url = self.DEFAULT_V2_BASE_URL if api_version == "v2" else self.DEFAULT_V1_BASE_URL
        if endpoint.startswith("http"): return endpoint
        return f"{base_url}/{endpoint.lstrip('/')}"

    def _get_headers(self, content_type: str = "json") -> dict:
        headers = {"X-Api-Key": self.api_key}
        if content_type and content_type.startswith(("image/", "video/", "audio/")):
            headers["Content-Type"] = content_type
        elif content_type == "json":  # For POST/PUT with JSON body
            headers["Content-Type"] = "application/json"
            headers["accept"] = "application/json"
        elif content_type == "accept_json":  # For GET/DELETE expecting JSON response, no body sent
            headers["accept"] = "application/json"
        return headers

    def upload_asset_from_bytes_get_image_key(self, file_bytes: bytes, file_name: str) -> str | None:
        self._log(f"Uploading image '{file_name}' from bytes to HeyGen assets.", "info")
        content_type, _ = mimetypes.guess_type(file_name)
        if not content_type or not content_type.startswith("image/"):
            ext = os.path.splitext(file_name)[1].lower()
            if ext in [".jpg", ".jpeg"]:
                content_type = "image/jpeg"
            elif ext == ".png":
                content_type = "image/png"
            else:
                self._log(f"File '{file_name}' not supported image type (bytes).", "error"); return None

        api_headers = self._get_headers(content_type=content_type)
        url = f"{self.DEFAULT_UPLOAD_URL}/asset"
        try:
            response = requests.post(url, headers=api_headers, data=file_bytes)
            response.raise_for_status();
            res_json = response.json()
            if response.status_code == 200 and res_json.get("data", {}).get("image_key"):
                self._log(f"Image from bytes uploaded. Image Key: {res_json['data']['image_key']}", "success")
                return res_json["data"]["image_key"]
            err_msg = res_json.get("error", {}).get("message", res_json.get("message", "Unknown error"));
            self._log(f"Asset upload (bytes) failed: {err_msg}", "error");
            return None
        except requests.exceptions.HTTPError as http_err:
            err_text = http_err.response.text[:500] if http_err.response else str(http_err);
            self._log(
                f"Asset upload (bytes) HTTP error: {http_err.response.status_code if http_err.response else 'N/A'} - {err_text}",
                "error");
            return None
        except json.JSONDecodeError:
            self._log(
                f"Asset upload (bytes) response not valid JSON. Status: {response.status_code if 'response' in locals() else 'N/A'}. Text: {response.text[:200] if 'response' in locals() else 'N/A'}",
                "error");
            return None
        except Exception as e:
            self._log(f"Unexpected error asset upload (bytes): {e}", "error"); return None

    def create_photo_avatar_group(self, name: str, image_key: str) -> str | None:
        url = self._get_api_url("photo_avatar/avatar_group/create", api_version="v2")  # As per original Streamlit
        payload = {"name": name, "image_key": image_key}
        self._log(f"Creating HeyGen avatar group '{name}' using image_key '{image_key}'", "info")
        try:
            response = requests.post(url, headers=self._get_headers("json"), json=payload)
            response.raise_for_status();
            data = response.json()
            if data.get("data", {}).get("group_id"):
                self._log(f"Group '{name}' created successfully. Group ID: {data['data']['group_id']}", "success");
                return data["data"]["group_id"]
            self._log(f"Group creation failed: {data.get('error', {}).get('message', 'Unknown')}", "error");
            return None
        except requests.exceptions.RequestException as e:
            self._log(f"Group creation request failed: {e}", "error");
            return None
        except json.JSONDecodeError:
            self._log(
                f"Group creation response not valid JSON. Status: {response.status_code if 'response' in locals() else 'N/A'}. Text: {response.text[:200] if 'response' in locals() else 'N/A'}",
                "error");
            return None

    def list_avatar_group_looks(self, group_id: str) -> list[dict] | None:
        url = self._get_api_url(f"avatar_group/{group_id}/avatars", api_version="v2")  # As per original Streamlit
        self._log(f"Listing looks for HeyGen avatar group ID '{group_id}'", "info")
        try:
            response = requests.get(url, headers=self._get_headers("accept_json"))
            response.raise_for_status();
            data = response.json()
            looks = data.get("data", {}).get("avatar_list", [])
            self._log(f"Fetched {len(looks)} Looks for group '{group_id}'", "success");
            return looks
        except requests.exceptions.RequestException as e:
            self._log(f"Failed to list group looks for group '{group_id}': {e}", "error");
            return None
        except json.JSONDecodeError:
            self._log(
                f"List looks response not valid JSON. Status: {response.status_code if 'response' in locals() else 'N/A'}. Text: {response.text[:200] if 'response' in locals() else 'N/A'}",
                "error");
            return None
        except KeyError:  # If 'data' or 'avatar_list' is missing
            self._log(
                f"List looks response missing expected keys. Response: {data if 'data' in locals() else 'Unknown Response'}",
                "error");
            return None

    def delete_photo_avatar_group(self, group_id: str) -> bool:
        """Deletes a Photo Avatar Group using DELETE with group_id in path."""
        if not group_id: self._log("Error: group_id cannot be empty for deletion.", "error"); return False
        url = self._get_api_url(f"photo_avatar_group/{group_id}", api_version="v2")
        self._log(f"Attempting to DELETE photo avatar group ID: {group_id} from URL: {url}", "info")
        api_headers = self._get_headers("accept_json")
        try:
            response = requests.delete(url, headers=api_headers)
            response.raise_for_status()
            if response.status_code == 200 or response.status_code == 204:
                if response.status_code == 200 and response.content:
                    try:
                        data = response.json()
                        if data.get("code") == 0 and "success" in data.get("message", "").lower():
                            self._log(f"Group '{group_id}' deleted successfully (DELETE, path param).", "success");
                            return True
                        self._log(f"Group delete for '{group_id}' (DELETE) was 200 OK but content unexpected: {data}",
                                  "warning");
                        return False
                    except json.JSONDecodeError:
                        self._log(
                            f"Group delete for '{group_id}' (DELETE) was 200 OK but response not JSON: {response.text[:200]}",
                            "warning");
                        return False
                else:  # 204 No Content or 200 with no content
                    self._log(f"Group '{group_id}' deleted successfully (DELETE, status {response.status_code}).",
                              "success");
                    return True
            self._log(f"Group delete for '{group_id}' (DELETE) failed with status {response.status_code}.", "error");
            return False
        except requests.exceptions.HTTPError as http_err:
            err_text = http_err.response.text[:200] if http_err.response else str(http_err)
            status_code = http_err.response.status_code if http_err.response else "N/A"
            if status_code == 404: self._log(f"Group ID '{group_id}' not found for deletion (DELETE).",
                                             "warning"); return True
            self._log(f"Group deletion HTTP error (DELETE, ID: {group_id}): {status_code} - {err_text}", "error");
            return False
        except Exception as e:
            self._log(f"Unexpected error deleting group (DELETE, ID: {group_id}): {e}", "error"); return False

    def delete_talking_photo(self, talking_photo_id: str) -> bool:
        if not talking_photo_id: self._log("No Talking Photo ID for deletion.", "warning"); return False
        url = self._get_api_url(f"talking_photos/{talking_photo_id}", api_version="v2")
        headers = self._get_headers(content_type="accept_json")
        self._log(f"Attempting to delete HeyGen talking photo ID: {talking_photo_id} from {url}", "info")
        try:
            response = requests.delete(url, headers=headers);
            response.raise_for_status()
            if response.status_code == 200 or response.status_code == 204:
                if response.status_code == 200 and response.content:
                    try:
                        data = response.json()
                        if data.get("code") == 0 and "success" in data.get("message", "").lower():
                            self._log(f"Talking photo '{talking_photo_id}' deleted.", "success");
                            return True
                        self._log(
                            f"Talking photo delete '{talking_photo_id}' was 200 OK but content unexpected: {data}",
                            "warning");
                        return False
                    except json.JSONDecodeError:
                        self._log(
                            f"Talking photo delete '{talking_photo_id}' was 200 OK but response not JSON: {response.text[:200]}",
                            "warning");
                        return False
                else:
                    self._log(f"Talking photo '{talking_photo_id}' deleted (status {response.status_code}).",
                              "success"); return True
            self._log(f"Talking photo deletion failed. Status: {response.status_code}", "error");
            return False
        except requests.exceptions.HTTPError as http_err:
            err_text = http_err.response.text[:200] if http_err.response else str(http_err)
            status_code = http_err.response.status_code if http_err.response else "N/A"
            if status_code == 404: self._log(f"Talking photo '{talking_photo_id}' not found for deletion.",
                                             "warning"); return True
            self._log(f"Talking photo deletion HTTP error (ID: {talking_photo_id}): {status_code} - {err_text}",
                      "error");
            return False
        except Exception as e:
            self._log(f"Unexpected error deleting talking photo (ID: {talking_photo_id}): {e}", "error"); return False

    def generate_video_with_photo_or_avatar(self, text_script: str, voice_id: str, title: str, test_mode: bool,
                                            add_caption: bool, dimension_preset: str, talking_photo_id: str = None,
                                            avatar_id: str = None) -> str | None:
        if not (talking_photo_id or avatar_id) or not voice_id: self._log("Error: Missing ID for video gen.",
                                                                          "error"); return None
        url = self._get_api_url("video/generate", api_version="v2")
        char_payload = {"type": "talking_photo" if talking_photo_id else "avatar",
                        ("talking_photo_id" if talking_photo_id else "avatar_id"): (
                            talking_photo_id if talking_photo_id else avatar_id)}
        video_inputs = [
            {"character": char_payload, "voice": {"type": "text", "input_text": text_script, "voice_id": voice_id}}]
        dim_map = {"16:9": {"width": 1920, "height": 1080}, "9:16": {"width": 1080, "height": 1920},
                   "1:1": {"width": 1080, "height": 1080}, "4:5": {"width": 1080, "height": 1350},
                   "720p": {"width": 1280, "height": 720}}
        dimension_payload = dim_map.get(dimension_preset)
        if not dimension_payload:
            try:
                w, h = map(int, dimension_preset.split('x')); dimension_payload = {"width": w, "height": h}
            except:
                dimension_payload = dim_map["720p"]; self._log(
                    f"Warn: Invalid custom dims '{dimension_preset}', using 720p", "warning")
        payload = {"video_inputs": video_inputs, "test": test_mode, "caption": add_caption,
                   "dimension": dimension_payload, "title": title}
        self._log(f"HeyGen generation payload: {json.dumps(payload, indent=1)}", "debug")
        try:
            response = requests.post(url, headers=self._get_headers("json"), json=payload);
            response.raise_for_status();
            data = response.json()
            if data.get("data", {}).get("video_id"):
                self._log(f"Video submission successful. ID: {data['data']['video_id']}", "success");
                return data["data"]["video_id"]
            self._log(f"Video submission failed: {data.get('error', {}).get('message', 'Unknown')}", "error");
            return None
        except requests.exceptions.RequestException as e:
            self._log(f"Video generation request failed: {e}", "error")
            if hasattr(e, 'response') and e.response is not None: self._log(
                f"HeyGen API Error Response: {e.response.text}", "error")
            return None
        except json.JSONDecodeError:
            self._log(
                f"Video gen response not valid JSON. Status: {response.status_code if 'response' in locals() else 'N/A'}. Text: {response.text[:200] if 'response' in locals() else 'N/A'}",
                "error");
            return None

    def check_video_status(self, video_id: str) -> tuple[str | None, str | None, dict | None]:
        url = self._get_api_url(f"video_status.get?video_id={video_id}", api_version="v1")
        self._log(f"Checking HeyGen video status for ID: {video_id}", "info")
        try:
            response = requests.get(url, headers=self._get_headers("accept_json"));
            response.raise_for_status();
            data = response.json()
            self._log(f"HeyGen status response: {data}", "debug")
            if data.get("data"): return data["data"].get("status"), data["data"].get("video_url"), data["data"].get(
                "error")
            self._log(f"Video status response format incorrect: {data}", "error");
            return "error", None, {"message": "Format error"}
        except requests.exceptions.RequestException as e:
            self._log(f"Failed to check video status (ID: {video_id}): {e}", "error");
            return "error", None, {"message": str(e)}
        except json.JSONDecodeError:
            self._log(
                f"Video status response not valid JSON. Status: {response.status_code if 'response' in locals() else 'N/A'}. Text: {response.text[:200] if 'response' in locals() else 'N/A'}",
                "error");
            return "error", None, {"message": "JSON decode error"}

    def list_avatar_groups(self) -> list[dict]:
        url = self._get_api_url("avatar_group.list", api_version="v2")  # Corrected as per original streamlit
        self._log(f"Requesting avatar group list from: {url}", "info")
        try:
            response = requests.get(url, headers=self._get_headers("accept_json"));
            response.raise_for_status();
            data = response.json()
            groups = data.get("data", {}).get("list", [])
            if not groups and isinstance(data.get("data"), list): groups = data.get("data")
            self._log(f"Fetched {len(groups)} avatar groups", "success");
            return groups
        except Exception as e:
            self._log(f"Fetch group list API failed: {e}", "error"); return []

    def train_photo_avatar_group(self, group_id: str) -> str | None:
        url = self._get_api_url("photo_avatar/train", api_version="v2")
        payload = {"group_id": group_id}
        self._log(f"Training avatar group: {group_id}")
        try:
            response = requests.post(url, headers=self._get_headers("json"), json=payload);
            response.raise_for_status();
            data = response.json()
            if response.ok:
                tid = data.get("data", {}).get("job_id") or data.get("data", {}).get("training_id")
                if tid: self._log(f"Group training submitted. TrackID:{tid}", "success"); return tid
            self._log(f"Error training group: {data.get('error', {}).get('message', 'Unknown')}", "error");
            return None
        except Exception as e:
            self._log(f"Train group API failed: {e}", "error"); return None

    def check_photo_avatar_group_training_status(self, training_id: str) -> tuple[str | None, dict | None]:
        url = self._get_api_url(f"photo_avatar/train/status/{training_id}", api_version="v2")
        try:
            response = requests.get(url, headers=self._get_headers("accept_json"));
            response.raise_for_status();
            data = response.json()
            d = data.get("data", {});
            status = d.get("status")
            err = d.get("error") or data.get("error");
            err_msg = err.get("message") if isinstance(err, dict) else str(err) if err else None
            if not status and err_msg: self._log(f"Group training status API error (ID:{training_id}):{err_msg}",
                                                 "error"); return "error", {"message": err_msg}
            return status, {"message": err_msg} if err_msg else None
        except Exception as e:
            self._log(f"Check group training status API failed: {e}", "error"); return "error", {"message": str(e)}