import streamlit as st
import requests
import time
import json
import os
import tempfile
import uuid
import mimetypes


# --- HeyGen API Functions ---
def get_api_urls(api_version="v2"):
    if api_version == "v1":
        return "https://api.heygen.com/v1"
    return "https://api.heygen.com/v2"


def get_headers(api_key, content_type="json"):
    headers = {"X-Api-Key": api_key}
    if content_type and (content_type.startswith("image/") or \
                         content_type.startswith("video/") or \
                         content_type.startswith("audio/")):
        headers["Content-Type"] = content_type
    elif content_type == "json":
        headers["Content-Type"] = "application/json"
    elif content_type == "accept_json":
        headers["accept"] = "application/json"
    return headers


def log_message(message, level="info"):
    print(f"LOG ({level.upper()}): {message}")
    if "logs" not in st.session_state:
        st.session_state.logs = []
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    st.session_state.logs = st.session_state.logs[-100:] + [formatted_message]


# --- Upload Asset Function (Corrected based on JSON structure) ---
def upload_asset_get_image_key(api_key, file_path, uploaded_file_name="uploaded_file.jpg"):
    if not os.path.exists(file_path):
        log_message(f"Error: Upload file not found: {file_path}", "error")
        st.error(f"Upload file error: Path {file_path} does not exist.")
        return None
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type or not content_type.startswith("image/"):
        ext = os.path.splitext(uploaded_file_name)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            content_type = "image/jpeg"
        elif ext == ".png":
            content_type = "image/png"
        else:
            log_message(f"Error: File '{uploaded_file_name}' is not a supported image type (jpg, png).", "error")
            st.error(f"File '{uploaded_file_name}' is not a supported image type (jpg, png).")
            return None
    log_message(f"Preparing to upload image asset: '{uploaded_file_name}', Content-Type: {content_type}")
    url = "https://upload.heygen.com/v1/asset"
    api_headers = get_headers(api_key, content_type=content_type)
    try:
        with open(file_path, "rb") as file_data:
            response = requests.post(url, headers=api_headers, data=file_data)
        log_message(f"Asset upload response status code: {response.status_code}")
        res_json = {}
        try:
            if response.content: res_json = response.json()
            log_message(f"Asset upload response JSON: {json.dumps(res_json, indent=2) if res_json else 'No JSON content'}")
        except json.JSONDecodeError:
            log_message(f"Asset upload response is not valid JSON. Status code: {response.status_code}. Text: {response.text[:200]}...",
                        "error")
            if not response.ok: response.raise_for_status()
            st.warning(f"File '{uploaded_file_name}' upload status code {response.status_code}, but response format is incorrect.")
            return None

        response.raise_for_status()

        if response.status_code == 200 and res_json and "data" in res_json and isinstance(res_json["data"], dict):
            api_data_obj = res_json["data"]
            asset_id = api_data_obj.get("id")
            file_type_from_api = api_data_obj.get("file_type")
            image_key_from_api = api_data_obj.get("image_key")

            if file_type_from_api == "image" and image_key_from_api:
                log_message(
                    f"Image asset '{uploaded_file_name}' uploaded successfully. Asset ID: {asset_id}, Image Key: {image_key_from_api}",
                    "success")
                st.success(f"Image '{uploaded_file_name}' uploaded successfully! Image Key: {image_key_from_api}")
                return image_key_from_api
            elif file_type_from_api != "image":
                log_message(
                    f"Uploaded file '{uploaded_file_name}' is not an image (API returned type: {file_type_from_api}). Asset ID: {asset_id}. No Image Key.",
                    "warning")
                st.warning(
                    f"Uploaded file '{uploaded_file_name}' is not an image (API returned type: {file_type_from_api}). Asset ID: {asset_id}. This Key cannot be used for photo avatars.")
                return None
            else:
                log_message(
                    f"Image asset '{uploaded_file_name}' uploaded successfully (API type: {file_type_from_api}), but image_key not found in response. Asset ID: {asset_id}",
                    "warning")
                st.warning(f"Image '{uploaded_file_name}' uploaded successfully but no image_key was returned.")
                return None
        else:
            err_msg = "Asset upload failed, response not as expected or missing data object."
            top_level_error = res_json.get("error")
            top_level_msg = res_json.get("msg") or res_json.get("message")

            if top_level_error is not None:
                if isinstance(top_level_error, dict) and "message" in top_level_error:
                    err_msg = top_level_error["message"]
                elif isinstance(top_level_error, str):
                    err_msg = top_level_error
                else:
                    err_msg = str(top_level_error)
            elif top_level_msg is not None:
                err_msg = top_level_msg

            log_message(f"Error: {err_msg}. Response: {res_json}", "error")
            st.error(f"Upload failed: {err_msg}")
            return None
    except requests.exceptions.HTTPError as http_err:
        err_text = http_err.response.text[:500] if hasattr(http_err,
                                                           'response') and http_err.response is not None else str(
            http_err)
        log_message(f"Asset upload API HTTP error: {http_err} - {err_text}", "error")
        status_code_err = http_err.response.status_code if hasattr(http_err,
                                                                   'response') and http_err.response is not None else 'Unknown'
        st.error(f"Upload request failed (HTTP {status_code_err}): {err_text}")
        return None
    except Exception as e:
        log_message(f"Unexpected error during asset upload API request: {e}", "error")
        st.error(f"Unexpected error during upload request: {e}")
        return None


# --- Video Avatar (for video) & Voice Functions ---
def upload_photo_avatar(api_key, image_path, avatar_name="My Custom Avatar"):
    if not os.path.exists(image_path): log_message(f"Error: Video avatar image file not found: {image_path}", "error"); return None
    url = f"{get_api_urls('v2')}/avatar/create_photo_avatar"
    log_message(f"Uploading photo to create video Avatar: {avatar_name} from {image_path}")
    files = {'photo': (os.path.basename(image_path), open(image_path, 'rb'))};
    data = {'name': avatar_name}
    try:
        response = requests.post(url, headers=get_headers(api_key, content_type=None), files=files, data=data)
        response.raise_for_status();
        res_json = response.json()
        if res_json.get("data", {}).get("avatar_id"):
            log_message(f"Photo video Avatar created successfully, ID: {res_json['data']['avatar_id']}", "success");
            return res_json["data"]["avatar_id"]
        else:
            log_message(f"Error: {res_json.get('error', {}).get('message', 'avatar_id not found in response')}. Details: {res_json}",
                        "error"); return None
    except Exception as e:
        log_message(f"Exception uploading photo video Avatar: {e}", "error"); return None
    finally:
        if 'photo' in files and files['photo'][1] and not files['photo'][1].closed: files['photo'][1].close()


def clone_voice_from_sample(api_key, audio_path, voice_name="My Cloned Voice"):
    if not os.path.exists(audio_path): log_message(f"Error: Voice sample file not found: {audio_path}", "error"); return None
    url = f"{get_api_urls('v1')}/voice";
    log_message(f"Uploading audio to clone voice: {voice_name}")
    ct, _ = mimetypes.guess_type(audio_path);
    if not ct or not ct.startswith("audio/"): ct = "audio/mpeg"
    files = {'files': (os.path.basename(audio_path), open(audio_path, 'rb'), ct)};
    data = {'name': voice_name}
    try:
        response = requests.post(url, headers=get_headers(api_key, content_type=None), files=files, data=data)
        response.raise_for_status();
        res_json = response.json()
        if res_json.get("data", {}).get("voice_id"):
            log_message(f"Voice cloned successfully, Voice ID: {res_json['data']['voice_id']}", "success");
            return res_json['data']['voice_id']
        else:
            log_message(f"Error: {res_json.get('error', {}).get('message', 'voice_id not found in response')}. Details:{res_json}",
                        "error"); return None
    except Exception as e:
        log_message(f"Cloning voice failed: {e}", "error"); return None
    finally:
        if 'files' in files and files['files'][1] and not files['files'][1].closed: files['files'][1].close()


# --- Video Generation (using Talking Photo or Standard Avatar) ---
def generate_video_with_photo_or_avatar(api_key, text_script, voice_id, title, test_mode, add_caption, dimension_preset,
                                        talking_photo_id=None, avatar_id=None):
    if not (talking_photo_id or avatar_id): log_message("Error: Must provide talking_photo_id or avatar_id to generate video.",
                                                        "error"); return None
    if not voice_id: log_message("Error: Must provide voice_id to generate video.", "error"); return None
    url = f"{get_api_urls('v2')}/video/generate"
    char_payload = {"type": "talking_photo" if talking_photo_id else "avatar",
                    ("talking_photo_id" if talking_photo_id else "avatar_id"): (
                        talking_photo_id if talking_photo_id else avatar_id)}
    log_message(
        f"Generating video using {'Talking Photo ID ' + talking_photo_id if talking_photo_id else 'Avatar ID ' + avatar_id}...")
    video_inputs = [
        {"character": char_payload, "voice": {"type": "text", "input_text": text_script, "voice_id": voice_id}}]
    dim = {};
    if dimension_preset == "16:9":
        dim = {"width": 1920, "height": 1080}
    elif dimension_preset == "9:16":
        dim = {"width": 1080, "height": 1920}
    elif dimension_preset == "1:1":
        dim = {"width": 1080, "height": 1080}
    elif dimension_preset == "4:5":
        dim = {"width": 1080, "height": 1350}
    else:
        try:
            w, h = map(int, dimension_preset.split('x')); dim = {"width": w, "height": h}
        except:
            dim = {"width": 1920, "height": 1080}; log_message("Warning: Invalid video dimensions, using 16:9", "warning")
    payload = {"video_inputs": video_inputs, "test": test_mode, "caption": add_caption, "dimension": dim,
               "title": title}
    print(payload)
    log_message(f"Sending video generation request (character type: {char_payload['type']})...");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()
        if data.get("data", {}).get("video_id"):
            return data["data"]["video_id"]
        else:
            log_message(f"Error: {data.get('error', {}).get('message', 'video_id not found in response')}. Details:{data}",
                        "error"); return None
    except Exception as e:
        log_message(f"Video generation request failed: {e}", "error"); return None


def check_heygen_video_status(api_key, video_id):
    url = f"{get_api_urls('v1')}/video_status.get?video_id={video_id}"
    try:
        response = requests.get(url, headers=get_headers(api_key, "accept_json"))
        response.raise_for_status();
        data = response.json()
        if data.get("data"):
            return data["data"].get("status"), data["data"].get("video_url"), data["data"].get("error")
        else:
            log_message(f"Error: Video status response format incorrect. Response: {data}", "error"); return "error", None, {
                "message": "Response format error"}
    except Exception as e:
        log_message(f"Failed to check video status (ID: {video_id}): {e}", "error"); return "error", None, {"message": str(e)}


# --- Photo Avatar Group Management Functions ---
def create_photo_avatar_group(api_key, name, key):
    url = f"{get_api_urls('v2')}/photo_avatar/avatar_group/create";
    payload = {"name": name, "image_key": key}
    log_message(f"Creating avatar group '{name}' using key '{key}'");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()
        if data.get("data", {}).get("group_id"):
            log_message(f"Group '{name}' created successfully, ID: {data['data']['group_id']}", "success");
            return data['data']['group_id']
        else:
            log_message(f"Error creating group: {data.get('error', {}).get('message', 'Unknown')}. Details:{data}",
                        "error"); return None
    except Exception as e:
        log_message(f"Create group API failed: {e}", "error"); return None


def add_looks_to_avatar_group(api_key, group_id, keys, name="look_collection"):
    url = f"{get_api_urls('v2')}/photo_avatar/avatar_group/add";
    payload = {"group_id": group_id, "image_keys": keys, "name": name}
    log_message(f"Adding {len(keys)} Looks to group {group_id} (collection:{name})");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()
        if response.ok and (not data or not data.get("error")):
            log_message(f"Looks successfully added to group {group_id}", "success");
            return True
        else:
            log_message(f"Failed to add Looks to group {group_id}: {data.get('error', {}).get('message', 'Unknown')}. Details:{data}",
                        "error"); return False
    except Exception as e:
        log_message(f"Add Looks API failed: {e}", "error"); return False


def train_photo_avatar_group(api_key, group_id):
    url = f"{get_api_urls('v2')}/photo_avatar/train";
    payload = {"group_id": group_id}
    log_message(f"Training avatar group: {group_id}");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()
        if response.ok:
            tid = data.get("data", {}).get("job_id") or data.get("data", {}).get("training_id") or group_id
            log_message(f"Group training submitted. GroupID:{group_id}, TrackID:{tid}", "success");
            return tid
        else:
            log_message(f"Error training group: {data.get('error', {}).get('message', 'Unknown')}. Details:{data}",
                        "error"); return None
    except Exception as e:
        log_message(f"Train group API failed: {e}", "error"); return None


def check_photo_avatar_group_training_status(api_key, training_id):
    url = f"{get_api_urls('v2')}/photo_avatar/train/status/{training_id}"
    try:
        response = requests.get(url, headers=get_headers(api_key, "accept_json"))
        response.raise_for_status();
        data = response.json()
        d = data.get("data", {});
        status = d.get("status");
        err = d.get("error") or data.get("error")
        err_msg = err.get("message") if isinstance(err, dict) else str(err) if err else None
        if not status and err_msg: log_message(f"Group training status API error (ID:{training_id}):{err_msg}",
                                               "error"); return "error", {"message": err_msg}
        return status, {"message": err_msg} if err_msg else None
    except Exception as e:
        log_message(f"Failed to check group training status API (ID:{training_id}):{e}", "error"); return "error", {"message": str(e)}


def list_avatar_groups(api_key):
    url = f"{get_api_urls('v2')}/avatar_group.list";
    log_message(f"Requesting avatar group list...");
    try:
        response = requests.get(url, headers=get_headers(api_key, "accept_json"))
        response.raise_for_status();
        data = response.json()
        groups = data.get("data", {}).get("list", [])
        if not groups and isinstance(data.get("data"), list): groups = data.get("data")
        if groups is not None:
            log_message(f"Successfully fetched {len(groups)} avatar groups", "success")
        elif data.get("error"):
            log_message(f"Error fetching group list API: {data.get('error', {}).get('message', 'Unknown')}", "error")
        else:
            log_message("Unknown response format for group list", "info")
        return groups if groups is not None else []
    except Exception as e:
        log_message(f"Fetch group list API failed: {e}", "error"); return []


def list_avatar_group_looks(api_key, group_id):
    url = f"{get_api_urls('v2')}/avatar_group/{group_id}/avatars";
    log_message(f"Requesting Looks list for group '{group_id}'...");
    try:
        response = requests.get(url, headers=get_headers(api_key, "accept_json"))
        response.raise_for_status();
        data = response.json()

        looks = data['data'].get("avatar_list", [])
        if looks is not None:
            log_message(f"Successfully fetched {len(looks)} Looks for group '{group_id}'", "success")
        elif data.get("error"):
            log_message(f"API error fetching Looks for group '{group_id}': {data.get('error', {}).get('message', 'Unknown')}", "error")
        else:
            log_message(f"Unknown response format for Looks list of group '{group_id}'", "info")
        return looks if looks is not None else []
    except Exception as e:
        log_message(f"Fetch Looks API for group '{group_id}' failed: {e}", "error"); return []


# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="HeyGen Photo Avatar Video Creator")
st.title("🎬 HeyGen Photo Avatar Video Creator")

# Initialize session state variables
default_api_key = "Y2JiMmYyZThlMzEwNDk3MGJhOTlhNDc1YWEwNGM5YTQtMTc0NzM3MTgwOA==" # Please use your own API key
for key, default_val in {
    "api_key": default_api_key, "logs": [],
    "video_id": None, "video_url": None, "video_status": None,
    "voice_id_to_use_for_video": st.session_state.get("ui_vid_voice_id_exist", "0093c2419a354e9995106a61791827ba"), # Example Voice ID
    "avatar_groups_list_for_vid": [], "selected_group_id_for_vid_looks": None,
    "group_looks_list_for_vid": [], "selected_talking_photo_id_for_vid": None,
    "group_id": None, "group_id_after_creation_flag": False, "current_group_name": None,
    "group_training_id": None, "group_training_status": None,
    "temp_initial_image_key_group_ui": None, "temp_look_image_keys_group_ui": [],
    "add_looks_status_msg_ui": None,
    "processing_type": None, "current_step": "idle",
    "last_displayed_log_count": 0,
    # UI input states
    "ui_grp_new_name": "", "ui_grp_initial_img_option": "Enter Image Key", "ui_grp_initial_img_key_direct": "",
    "ui_grp_addlooks_groupid": "", "ui_grp_addlooks_name": "additional_looks", "ui_grp_addlooks_keys_text": "",
    "ui_grp_train_groupid": "",
    "ui_vid_script": "Hello, welcome to the HeyGen Photo Avatar video feature!", "ui_vid_title": "My Avatar Group Video",
    "ui_vid_test_mode": True, "ui_vid_add_captions": True, "ui_vid_dimension": "1280x720",
    "ui_vid_voice_option": "Use Existing Voice ID", "ui_vid_voice_id_exist": "d7bbcdd6964c47bdaae26decade4a933", # Example Voice ID
    "ui_vid_voice_name_new": "MyClonedVidVoice",
    "ui_vid_groupid_for_look_select": ""
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_val

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ API Settings")
    is_processing_main_ui_app = (st.session_state.current_step != "idle")
    st.session_state.api_key = st.text_input("HeyGen API Key", value=st.session_state.api_key, type="password",
                                             disabled=is_processing_main_ui_app,
                                             key="api_key_input_sidebar_final_app_main_key_v2")

    st.header("🛠️ Select Operation")
    operation_type_main_ui_app = st.radio(
        "What would you like to do?",
        ("Manage Photo Avatar Groups", "Generate Video (using a Look from a Photo Avatar Group)"),
        key="operation_choice_main_sidebar_app_key_v2",
        horizontal=False,
        disabled=is_processing_main_ui_app
    )

# --- Log Display Area ---
status_placeholder_main_ui_app = st.empty()
log_placeholder_main_ui_app = st.empty()


def display_logs_main_ui_app_final():
    with log_placeholder_main_ui_app.container():
        st.text_area("Logs", value="\n".join(st.session_state.logs[-50:]),
                     height=250, key="log_display_area_main_unique_final_app_main_app_key_v2", disabled=True)


# --- UI Sections ---
if operation_type_main_ui_app == "Manage Photo Avatar Groups":
    st.header("🖼️ Photo Avatar Group Management")
    st.caption("Steps 1 & 2: Create a group and add images. Step 3: Train the group for better consistency.")

    if st.session_state.group_id:
        st.success(
            f"Current operating Group ID: **{st.session_state.group_id}** (Group Name: {st.session_state.current_group_name or 'Unnamed'})")
    if st.session_state.group_training_status and st.session_state.group_training_status != "Ready" and st.session_state.current_step == "idle" and st.session_state.group_id:
        st.warning(f"Group {st.session_state.group_id}'s training status is: {st.session_state.group_training_status}.")

    group_action_main_ui_val = st.selectbox(
        "Select group management action:",
        ["(Select action)", "1. Create New Avatar Group", "2. Add Images (Looks) to Group", "3. Train Avatar Group"],
        key="group_action_choice_main_app_key_v2",
        disabled=is_processing_main_ui_app
    )

    if group_action_main_ui_val == "1. Create New Avatar Group":
        st.subheader("1. Create New Photo Avatar Group")
        st.session_state.ui_grp_new_name = st.text_input("New Group Name:", value=st.session_state.ui_grp_new_name,
                                                         key="ui_grp_new_name_key_v2",
                                                         disabled=is_processing_main_ui_app)
        st.markdown("**Initial Image (for group creation):**")
        st.session_state.ui_grp_initial_img_option = st.radio("Initial Image Source:", ("Enter Image Key", "Upload Image"),
                                                              key="ui_grp_initial_img_option_key_v2",
                                                              index=["Enter Image Key", "Upload Image"].index(
                                                                  st.session_state.ui_grp_initial_img_option),
                                                              horizontal=True, disabled=is_processing_main_ui_app)
        initial_image_key_for_creation_val_ui = ""
        if st.session_state.ui_grp_initial_img_option == "Enter Image Key":
            st.session_state.ui_grp_initial_img_key_direct = st.text_input("Initial Image's Image Key:",
                                                                           value=st.session_state.ui_grp_initial_img_key_direct,
                                                                           placeholder="e.g., image/xxxx/original",
                                                                           key="ui_grp_initial_img_key_direct_key_v2",
                                                                           disabled=is_processing_main_ui_app)
            initial_image_key_for_creation_val_ui = st.session_state.ui_grp_initial_img_key_direct
        elif st.session_state.ui_grp_initial_img_option == "Upload Image":
            uploaded_initial_img_grp_main_ui_val = st.file_uploader("Upload Initial Image:", type=["jpg", "png", "jpeg"],
                                                                    key="ui_grp_initial_img_uploader_key_v2",
                                                                    disabled=is_processing_main_ui_app)
            if uploaded_initial_img_grp_main_ui_val:
                if st.button("Upload and Get Key (Initial Image)", key="ui_grp_upload_initial_btn_key_v2",
                             disabled=is_processing_main_ui_app):
                    with tempfile.NamedTemporaryFile(delete=False,
                                                     suffix=os.path.splitext(uploaded_initial_img_grp_main_ui_val.name)[
                                                         1]) as tmp_f:
                        tmp_f.write(uploaded_initial_img_grp_main_ui_val.getvalue());
                        temp_f_path = tmp_f.name
                    actual_key = upload_asset_get_image_key(st.session_state.api_key, temp_f_path,
                                                            uploaded_initial_img_grp_main_ui_val.name)
                    st.session_state.temp_initial_image_key_group_ui = actual_key if actual_key else None
                    os.unlink(temp_f_path)
            retrieved_key_create = st.session_state.get("temp_initial_image_key_group_ui")
            if retrieved_key_create: initial_image_key_for_creation_val_ui = retrieved_key_create

        if st.button("➡️ Create Avatar Group", key="ui_grp_create_btn_key_v2",
                     disabled=is_processing_main_ui_app or not st.session_state.ui_grp_new_name or not initial_image_key_for_creation_val_ui):
            st.session_state.processing_type = "avatar_group_manage";
            st.session_state.current_step = "group_create"
            st.session_state.current_group_name_for_creation = st.session_state.ui_grp_new_name
            st.session_state.current_initial_image_key_for_creation = initial_image_key_for_creation_val_ui
            for key_to_reset in ["group_id", "group_id_after_creation_flag", "group_training_id",
                                 "group_training_status", "current_group_name", "add_looks_status_msg_ui"]:
                st.session_state[key_to_reset] = False if key_to_reset == "group_id_after_creation_flag" else None
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0
            log_message(f"Starting creation of photo avatar group '{st.session_state.ui_grp_new_name}'...")
            st.rerun()

    elif group_action_main_ui_val == "2. Add Images (Looks) to Group":
        st.subheader("2. Add Images (Looks) to Group")
        if st.session_state.get("add_looks_status_msg_ui"):
            if "successfully" in st.session_state.add_looks_status_msg_ui.lower():
                st.success(st.session_state.add_looks_status_msg_ui)
            else:
                st.error(st.session_state.add_looks_status_msg_ui)
            st.session_state.add_looks_status_msg_ui = None # Clear after displaying

        st.session_state.ui_grp_addlooks_groupid = st.text_input("Target Group ID:",
                                                                 value=st.session_state.ui_grp_addlooks_groupid or st.session_state.get(
                                                                     "group_id", ""),
                                                                 key="ui_grp_addlooks_groupid_key_v2",
                                                                 disabled=is_processing_main_ui_app)
        st.session_state.ui_grp_addlooks_name = st.text_input("Name/Description for these Looks (Optional):",
                                                              value=st.session_state.ui_grp_addlooks_name,
                                                              key="ui_grp_addlooks_name_key_v2",
                                                              disabled=is_processing_main_ui_app)
        st.markdown("**Images to Add (Provide Image Keys):** (One per line)")
        st.session_state.ui_grp_addlooks_keys_text = st.text_area("Image Keys:",
                                                                  value=st.session_state.ui_grp_addlooks_keys_text,
                                                                  placeholder="image/key1/original\nimage/key2/original",
                                                                  height=100, key="ui_grp_addlooks_keys_text_key_v2",
                                                                  disabled=is_processing_main_ui_app)
        st.markdown("Or **Upload Images (to get Keys):**")
        uploaded_looks_add_grp_main_ui_val = st.file_uploader("Upload one or more images as Looks:",
                                                              type=["jpg", "png", "jpeg"], accept_multiple_files=True,
                                                              key="ui_grp_addlooks_uploader_key_v2",
                                                              disabled=is_processing_main_ui_app)
        if uploaded_looks_add_grp_main_ui_val:
            if st.button("Upload Selected Images and Get Keys (Looks)", key="ui_grp_addlooks_upload_btn_key_v2",
                         disabled=is_processing_main_ui_app):
                st.session_state.temp_look_image_keys_group_ui = []
                for uploaded_file in uploaded_looks_add_grp_main_ui_val:
                    with tempfile.NamedTemporaryFile(delete=False,
                                                     suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_f:
                        tmp_f.write(uploaded_file.getvalue());
                        temp_f_path = tmp_f.name
                    actual_key = upload_asset_get_image_key(st.session_state.api_key, temp_f_path, uploaded_file.name)
                    if actual_key: st.session_state.temp_look_image_keys_group_ui.append(actual_key)
                    os.unlink(temp_f_path)
        current_temp_keys_add_looks_val = st.session_state.get("temp_look_image_keys_group_ui", [])
        final_keys_to_add_val = [key.strip() for key in st.session_state.ui_grp_addlooks_keys_text.splitlines() if
                                 key.strip()]
        if current_temp_keys_add_looks_val: final_keys_to_add_val.extend(current_temp_keys_add_looks_val)
        final_keys_to_add_val = list(set(final_keys_to_add_val))
        if st.button("➡️ Add Looks to Group", key="ui_grp_addlooks_submit_btn_key_v2",
                     disabled=is_processing_main_ui_app or not st.session_state.ui_grp_addlooks_groupid or not final_keys_to_add_val):
            st.session_state.processing_type = "avatar_group_manage";
            st.session_state.current_step = "group_add_looks"
            st.session_state.current_group_id_for_add_looks = st.session_state.ui_grp_addlooks_groupid
            st.session_state.current_image_keys_for_add_looks = final_keys_to_add_val
            st.session_state.current_look_name_for_add_looks = st.session_state.ui_grp_addlooks_name
            st.session_state.add_looks_status_msg_ui = None
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0
            log_message(f"Starting to add Looks to group '{st.session_state.ui_grp_addlooks_groupid}'...")
            st.rerun()

    elif group_action_main_ui_val == "3. Train Avatar Group":
        st.subheader("3. Train Avatar Group")
        st.session_state.ui_grp_train_groupid = st.text_input("Group ID to train:",
                                                              value=st.session_state.ui_grp_train_groupid or st.session_state.get(
                                                                  "group_id", ""), key="ui_grp_train_groupid_key_v2",
                                                              disabled=is_processing_main_ui_app)
        if st.button("➡️ Start Group Training", key="ui_grp_train_btn_key_v2",
                     disabled=is_processing_main_ui_app or not st.session_state.ui_grp_train_groupid):
            st.session_state.processing_type = "avatar_group_manage";
            st.session_state.current_step = "group_train_request"
            st.session_state.current_group_id_for_train = st.session_state.ui_grp_train_groupid
            st.session_state.group_training_id, st.session_state.group_training_status = None, "Requesting training start..."
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0
            log_message(f"Starting training for photo avatar group '{st.session_state.ui_grp_train_groupid}'...")
            st.rerun()

elif operation_type_main_ui_app == "Generate Video (using a Look from a Photo Avatar Group)":
    st.header("📹 Generate Video Using Photo Avatar Group")
    st.session_state.ui_vid_groupid_for_look_select = st.text_input("Target Avatar Group ID:",
                                                                    value=st.session_state.ui_vid_groupid_for_look_select or st.session_state.get(
                                                                        "group_id", ""),
                                                                    key="ui_vid_groupid_for_look_select_key_v2",
                                                                    disabled=is_processing_main_ui_app)

    if st.session_state.ui_vid_groupid_for_look_select:
        if st.button("Load Looks from Group", key="ui_vid_load_looks_btn_key_v2", disabled=is_processing_main_ui_app):
            st.session_state.group_looks_list_for_vid = list_avatar_group_looks(st.session_state.api_key,
                                                                                st.session_state.ui_vid_groupid_for_look_select)
            if not st.session_state.group_looks_list_for_vid: st.warning("No Looks found or failed to load.")
            st.session_state.selected_talking_photo_id_for_vid = None
            st.rerun()

        if st.session_state.group_looks_list_for_vid:
            look_options_for_vid_val = {}
            for i, look_data in enumerate(st.session_state.group_looks_list_for_vid):
                tp_id = look_data.get("talking_photo_id") or look_data.get("id") or look_data.get(
                    "image_key")
                look_name = look_data.get("name", f"Look {i + 1}") + (f" (ID: ...{tp_id[-6:]})" if tp_id else "")
                if tp_id: look_options_for_vid_val[tp_id] = look_name

            if look_options_for_vid_val:
                current_selection_vid_look = st.session_state.selected_talking_photo_id_for_vid
                if current_selection_vid_look not in look_options_for_vid_val: current_selection_vid_look = None

                st.session_state.selected_talking_photo_id_for_vid = st.selectbox(
                    "Select a Look as the video character:", options=list(look_options_for_vid_val.keys()),
                    format_func=lambda x: look_options_for_vid_val.get(x, x),
                    index=list(look_options_for_vid_val.keys()).index(
                        current_selection_vid_look) if current_selection_vid_look else 0,
                    key="ui_vid_select_talking_photo_key_v2", disabled=is_processing_main_ui_app,
                    placeholder="Select a photo avatar..."
                )
            else:
                st.write("This group has no available Looks or their IDs could not be resolved to Talking Photo IDs.")
        elif st.session_state.ui_vid_groupid_for_look_select:
            st.write("Click 'Load Looks from Group' to select.")

    with st.expander("Voice Settings (Video)", expanded=True):
        st.session_state.ui_vid_voice_option = st.radio("Select Voice Source:", ("Clone New Voice", "Use Existing Voice ID"),
                                                        key="ui_vid_voice_option_grp_vid_key_v2",
                                                        index=["Clone New Voice", "Use Existing Voice ID"].index(
                                                            st.session_state.ui_vid_voice_option),
                                                        disabled=is_processing_main_ui_app)
        if st.session_state.ui_vid_voice_option == "Clone New Voice":
            uploaded_voice_sample_grp_vid_ui_val = st.file_uploader("Upload Voice Sample", type=["mp3", "wav"],
                                                                    key="ui_vid_voice_uploader_grp_vid_key_v2",
                                                                    disabled=is_processing_main_ui_app)
            st.session_state.ui_vid_voice_name_new = st.text_input("New Voice Name",
                                                                   value=st.session_state.ui_vid_voice_name_new,
                                                                   key="ui_vid_voice_name_new_grp_vid_key_v2",
                                                                   disabled=is_processing_main_ui_app)
        else:
            st.session_state.ui_vid_voice_id_exist = st.text_input("Existing Voice ID",
                                                                   value=st.session_state.ui_vid_voice_id_exist,
                                                                   key="ui_vid_voice_id_exist_grp_vid_key_v2",
                                                                   disabled=is_processing_main_ui_app)

    st.subheader("📝 Video Content and Parameters")
    st.session_state.ui_vid_script = st.text_area("Video Script", value=st.session_state.ui_vid_script,
                                                  key="ui_vid_script_grp_vid_key_v2",
                                                  disabled=is_processing_main_ui_app)
    st.session_state.ui_vid_title = st.text_input("Video Title", value=st.session_state.ui_vid_title,
                                                  key="ui_vid_title_grp_vid_key_v2", disabled=is_processing_main_ui_app)
    c1_grp_vid_val, c2_grp_vid_val, c3_grp_vid_val = st.columns(3)
    dimension_options_grp_vid_val = ["16:9", "9:16", "1:1", "4:5", "1280x720", "1920x1080"]
    st.session_state.ui_vid_test_mode = c1_grp_vid_val.checkbox("Test Mode", value=st.session_state.ui_vid_test_mode,
                                                                key="ui_vid_test_mode_grp_vid_key_v2",
                                                                disabled=is_processing_main_ui_app)
    st.session_state.ui_vid_add_captions = c2_grp_vid_val.checkbox("Add Captions",
                                                                   value=st.session_state.ui_vid_add_captions,
                                                                   key="ui_vid_add_captions_grp_vid_key_v2",
                                                                   disabled=is_processing_main_ui_app)
    st.session_state.ui_vid_dimension = c3_grp_vid_val.selectbox("Video Dimensions", dimension_options_grp_vid_val,
                                                                 index=dimension_options_grp_vid_val.index(
                                                                     st.session_state.ui_vid_dimension) if st.session_state.ui_vid_dimension in dimension_options_grp_vid_val else 0,
                                                                 key="ui_vid_dimension_grp_vid_key_v2",
                                                                 disabled=is_processing_main_ui_app)

    st.markdown("---")
    if st.button("🚀 Generate Avatar Group Video",
                 disabled=is_processing_main_ui_app or not st.session_state.selected_talking_photo_id_for_vid,
                 key="ui_vid_generate_grp_vid_btn_key_v2"):
        if not st.session_state.api_key.strip():
            st.error("API Key is missing!")
        elif not st.session_state.ui_vid_script.strip():
            st.error("Video script is missing!")
        else:
            st.session_state.processing_type = "video_from_group_look"
            st.session_state.current_step = "video_from_group_get_voice_id"
            for key_to_reset in ["video_id", "video_url", "voice_id_to_use_for_video"]: st.session_state[
                key_to_reset] = None
            st.session_state.video_status = "Starting video processing (avatar group)..."
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0

            if st.session_state.ui_vid_voice_option == "Clone New Voice" and uploaded_voice_sample_grp_vid_ui_val is not None:
                st.session_state.temp_uploaded_voice_bytes_for_grp_vid = uploaded_voice_sample_grp_vid_ui_val.getvalue()
                st.session_state.temp_uploaded_voice_filename_for_grp_vid = uploaded_voice_sample_grp_vid_ui_val.name
            else:
                st.session_state.temp_uploaded_voice_bytes_for_grp_vid = None
                st.session_state.temp_uploaded_voice_filename_for_grp_vid = None

            log_message("Starting video generation process using avatar group Look...")
            st.rerun()

    if st.session_state.video_url and st.session_state.current_step == "idle" and \
       st.session_state.processing_type == "video_from_group_look" and st.session_state.video_status == "completed":
        st.success(f"Video generated successfully! You can watch it below or download it from: {st.session_state.video_url}")
        st.video(st.session_state.video_url)


# --- Processing Logic ---
if st.session_state.current_step != "idle":
    with status_placeholder_main_ui_app.container():
        pass

    if st.session_state.processing_type == "video_from_group_look":
        if st.session_state.current_step == "video_from_group_get_voice_id":
            log_message("Video (Avatar Group) Step 1: Determining Voice ID...")
            voice_id_to_set_for_grp_vid = None
            if st.session_state.ui_vid_voice_option == "Clone New Voice":
                if st.session_state.get("temp_uploaded_voice_bytes_for_grp_vid"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=
                    os.path.splitext(st.session_state.temp_uploaded_voice_filename_for_grp_vid)[1]) as tmp_f:
                        tmp_f.write(st.session_state.temp_uploaded_voice_bytes_for_grp_vid);
                        temp_path = tmp_f.name
                    voice_name = st.session_state.ui_vid_voice_name_new or "GrpVidClonedVoice"
                    voice_id_to_set_for_grp_vid = clone_voice_from_sample(st.session_state.api_key, temp_path,
                                                                          voice_name)
                    os.unlink(temp_path);
                    if voice_id_to_set_for_grp_vid: time.sleep(10)
                    st.session_state.temp_uploaded_voice_bytes_for_grp_vid = None
                    st.session_state.temp_uploaded_voice_filename_for_grp_vid = None
                else:
                    log_message("Warning: Failed to process uploaded voice sample file (avatar group video).", "warning")
            else:
                voice_id_to_set_for_grp_vid = st.session_state.ui_vid_voice_id_exist

            st.session_state.voice_id_to_use_for_video = voice_id_to_set_for_grp_vid
            if not st.session_state.voice_id_to_use_for_video:
                log_message("Error: Failed to determine Voice ID (avatar group video).", "error"); st.session_state.current_step = "idle"
            else:
                log_message(
                    f"Using Voice ID: {st.session_state.voice_id_to_use_for_video} (avatar group video)"); st.session_state.current_step = "video_from_group_generate_request"
            st.rerun()

        elif st.session_state.current_step == "video_from_group_generate_request":
            log_message("Video (Avatar Group) Step 2: Submitting video generation request...")
            if not st.session_state.selected_talking_photo_id_for_vid or not st.session_state.voice_id_to_use_for_video:
                log_message("Error: Missing Talking Photo ID or Voice ID (avatar group video).", "error");
                st.session_state.current_step = "idle"
            else:
                video_id_res_grp_vid = generate_video_with_photo_or_avatar(
                    st.session_state.api_key, st.session_state.ui_vid_script,
                    st.session_state.voice_id_to_use_for_video,
                    st.session_state.ui_vid_title, st.session_state.ui_vid_test_mode,
                    st.session_state.ui_vid_add_captions,
                    st.session_state.ui_vid_dimension,
                    talking_photo_id=st.session_state.selected_talking_photo_id_for_vid
                )
                if video_id_res_grp_vid:
                    st.session_state.video_id = video_id_res_grp_vid;
                    st.session_state.video_status = "Video (avatar group) submitted..."
                    log_message(f"Video (avatar group) request submitted, ID: {video_id_res_grp_vid}");
                    st.session_state.current_step = "video_from_group_poll_status"
                else:
                    st.session_state.video_status = "Video (avatar group) request failed."; st.session_state.current_step = "idle"
            st.rerun()

        elif st.session_state.current_step == "video_from_group_poll_status" and st.session_state.video_id:
            status_grp_vid, url_grp_vid, err_grp_vid = check_heygen_video_status(st.session_state.api_key,
                                                                                 st.session_state.video_id)
            is_final_grp_vid = False
            if status_grp_vid == "completed":
                st.session_state.video_url = url_grp_vid; log_message(f"Video (avatar group) generation completed! URL: {url_grp_vid}",
                                                                      "success"); st.session_state.current_step = "idle"; is_final_grp_vid = True
            elif status_grp_vid == "failed":
                msg_grp_vid = err_grp_vid.get('message', 'Unknown') if isinstance(err_grp_vid, dict) else str(
                    err_grp_vid); log_message(f"Video (avatar group) generation failed: {msg_grp_vid}",
                                              "error"); st.session_state.current_step = "idle"; is_final_grp_vid = True
            elif status_grp_vid == "error":
                msg_grp_vid = err_grp_vid.get('message', 'API call error') if isinstance(err_grp_vid, dict) else str(
                    err_grp_vid); log_message(f"Error checking video (avatar group) status: {status_grp_vid}, {msg_grp_vid}",
                                              "error"); st.session_state.current_step = "idle"; is_final_grp_vid = True
            st.session_state.video_status = status_grp_vid
            if is_final_grp_vid:
                st.rerun()
            else:
                log_message(f"Polling video (avatar group) status: {status_grp_vid}"); time.sleep(10); st.rerun()

    elif st.session_state.processing_type == "avatar_group_manage":
        if st.session_state.current_step == "group_create":
            log_message(f"Processing: Creating group '{st.session_state.current_group_name_for_creation}'...")
            group_id_res_grp_proc_val_logic_final_val_manage = create_photo_avatar_group(st.session_state.api_key,
                                                                                         st.session_state.current_group_name_for_creation,
                                                                                         st.session_state.current_initial_image_key_for_creation)
            if group_id_res_grp_proc_val_logic_final_val_manage:
                st.session_state.group_id = group_id_res_grp_proc_val_logic_final_val_manage
                st.session_state.group_id_after_creation_flag = True
                st.session_state.current_group_name = st.session_state.current_group_name_for_creation
                log_message(
                    f"Group '{st.session_state.current_group_name}' created successfully, ID: {group_id_res_grp_proc_val_logic_final_val_manage}",
                    "success")
            else:
                log_message(f"Failed to create group '{st.session_state.current_group_name_for_creation}'.", "error")
            st.session_state.current_step = "idle"
            st.session_state.temp_initial_image_key_group_ui = None
            st.rerun()

        elif st.session_state.current_step == "group_add_looks":
            log_message(f"Processing: Adding Looks to group '{st.session_state.current_group_id_for_add_looks}'...")
            success_add_looks_val_proc_val_logic_final_val_manage = add_looks_to_avatar_group(st.session_state.api_key,
                                                                                              st.session_state.current_group_id_for_add_looks,
                                                                                              st.session_state.current_image_keys_for_add_looks,
                                                                                              st.session_state.current_look_name_for_add_looks)
            if success_add_looks_val_proc_val_logic_final_val_manage:
                st.session_state.add_looks_status_msg_ui = f"Looks successfully added to group '{st.session_state.current_group_id_for_add_looks}'."
            else:
                st.session_state.add_looks_status_msg_ui = f"Failed to add Looks to group '{st.session_state.current_group_id_for_add_looks}'."
            st.session_state.current_step = "group_add_looks_status"
            st.session_state.temp_look_image_keys_group_ui = []
            st.rerun()

        elif st.session_state.current_step == "group_add_looks_status":
            # Message is displayed in UI section, then current_step should become idle
            st.session_state.current_step = "idle"
            st.rerun() # Rerun to reflect idle state and show message

        elif st.session_state.current_step == "group_train_request":
            log_message(f"Processing: Initiating training for group '{st.session_state.current_group_id_for_train}'...")
            training_id_val_grp_proc_val_logic_final_val_manage = train_photo_avatar_group(st.session_state.api_key,
                                                                                           st.session_state.current_group_id_for_train)
            if training_id_val_grp_proc_val_logic_final_val_manage:
                st.session_state.group_training_id = training_id_val_grp_proc_val_logic_final_val_manage
                st.session_state.group_training_status = "Training submitted, awaiting processing..."
                log_message(f"Group training submitted/started. Tracking ID: {training_id_val_grp_proc_val_logic_final_val_manage}")
                st.session_state.current_step = "group_poll_train_status"
            else:
                log_message(f"Failed to initiate training for group '{st.session_state.current_group_id_for_train}'.", "error")
                st.session_state.group_training_status = "Training initiation failed";
                st.session_state.current_step = "idle"
            st.rerun()

        elif st.session_state.current_step == "group_poll_train_status" and st.session_state.group_training_id:
            status_train_poll_grp_proc_val_logic_final_val_manage, err_info_train_poll_grp_proc_val_logic_final_val_manage = check_photo_avatar_group_training_status(
                st.session_state.api_key, st.session_state.group_training_id)
            is_final_train_poll_grp_proc_val_logic_final_val_manage = False
            if status_train_poll_grp_proc_val_logic_final_val_manage == "Ready":
                log_message(f"Avatar group (ID: {st.session_state.group_training_id}) training completed!", "success");
                st.session_state.current_step = "idle";
                is_final_train_poll_grp_proc_val_logic_final_val_manage = True
            elif status_train_poll_grp_proc_val_logic_final_val_manage == "Failed" or status_train_poll_grp_proc_val_logic_final_val_manage == "Error":
                err_train_poll_grp_msg_proc_val_logic_final_val_manage = err_info_train_poll_grp_proc_val_logic_final_val_manage.get(
                    "message", "Unknown training error") if isinstance(err_info_train_poll_grp_proc_val_logic_final_val_manage,
                                                             dict) else str(
                    err_info_train_poll_grp_proc_val_logic_final_val_manage)
                log_message(
                    f"Avatar group (ID: {st.session_state.group_training_id}) training failed. Reason: {err_train_poll_grp_msg_proc_val_logic_final_val_manage}",
                    "error");
                st.session_state.current_step = "idle";
                is_final_train_poll_grp_proc_val_logic_final_val_manage = True

            st.session_state.group_training_status = status_train_poll_grp_proc_val_logic_final_val_manage
            if is_final_train_poll_grp_proc_val_logic_final_val_manage:
                st.rerun()
            elif status_train_poll_grp_proc_val_logic_final_val_manage in ["Pending", "Training"]:
                log_message(
                    f"Polling avatar group training status (ID: {st.session_state.group_training_id}): {status_train_poll_grp_proc_val_logic_final_val_manage}");
                time.sleep(10);
                st.rerun()
            else: # Includes any other unexpected statuses
                log_message(
                    f"Received unknown training status '{status_train_poll_grp_proc_val_logic_final_val_manage}' or error during check (ID: {st.session_state.group_training_id})",
                    "warning")
                if err_info_train_poll_grp_proc_val_logic_final_val_manage and err_info_train_poll_grp_proc_val_logic_final_val_manage.get("message"):
                     log_message(f"Error details: {err_info_train_poll_grp_proc_val_logic_final_val_manage.get('message')}", "warning")

                st.session_state.current_step = "idle";
                st.rerun()


# --- Final Log Display ---
if st.session_state.logs:
    display_logs_main_ui_app_final()