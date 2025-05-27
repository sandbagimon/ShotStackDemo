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
        log_message(f"错误: 上传文件未找到: {file_path}", "error")
        st.error(f"上传文件错误: 路径 {file_path} 不存在。")
        return None
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type or not content_type.startswith("image/"):
        ext = os.path.splitext(uploaded_file_name)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            content_type = "image/jpeg"
        elif ext == ".png":
            content_type = "image/png"
        else:
            log_message(f"错误: 文件 '{uploaded_file_name}' 不是支持的图片类型 (jpg, png)。", "error")
            st.error(f"文件 '{uploaded_file_name}' 不是支持的图片类型 (jpg, png)。")
            return None
    log_message(f"准备上传图片资源: '{uploaded_file_name}', Content-Type: {content_type}")
    url = "https://upload.heygen.com/v1/asset"
    api_headers = get_headers(api_key, content_type=content_type)
    try:
        with open(file_path, "rb") as file_data:
            response = requests.post(url, headers=api_headers, data=file_data)
        log_message(f"上传资源响应状态码: {response.status_code}")
        res_json = {}
        try:
            if response.content: res_json = response.json()
            log_message(f"上传资源响应 JSON: {json.dumps(res_json, indent=2) if res_json else 'No JSON content'}")
        except json.JSONDecodeError:
            log_message(f"上传资源响应不是有效的JSON. 状态码: {response.status_code}. Text: {response.text[:200]}...",
                        "error")
            if not response.ok: response.raise_for_status()
            st.warning(f"文件 '{uploaded_file_name}' 上传状态码 {response.status_code}，但响应格式错误。")
            return None

        response.raise_for_status()

        # Correctly access nested "data" object based on your provided successful JSON
        if response.status_code == 200 and res_json and "data" in res_json and isinstance(res_json["data"], dict):
            api_data_obj = res_json["data"]
            asset_id = api_data_obj.get("id")
            file_type_from_api = api_data_obj.get("file_type")
            image_key_from_api = api_data_obj.get("image_key")

            if file_type_from_api == "image" and image_key_from_api:
                log_message(
                    f"图片资源 '{uploaded_file_name}' 上传成功. Asset ID: {asset_id}, Image Key: {image_key_from_api}",
                    "success")
                st.success(f"图片 '{uploaded_file_name}' 上传成功! Image Key: {image_key_from_api}")
                return image_key_from_api
            elif file_type_from_api != "image":
                log_message(
                    f"上传的文件 '{uploaded_file_name}' 不是图片 (API返回类型: {file_type_from_api}). Asset ID: {asset_id}. 没有 Image Key。",
                    "warning")
                st.warning(
                    f"上传的文件 '{uploaded_file_name}' 不是图片 (API返回类型: {file_type_from_api})。Asset ID: {asset_id}。此 Key 不可用于照片头像。")
                return None
            else:
                log_message(
                    f"图片资源 '{uploaded_file_name}' 上传成功 (API类型: {file_type_from_api})，但响应中未找到 image_key. Asset ID: {asset_id}",
                    "warning")
                st.warning(f"图片 '{uploaded_file_name}' 上传成功但未返回 image_key。")
                return None
        else:
            # Handle cases where 'data' might be missing or not a dict, or other errors
            err_msg = "上传资源失败，响应不符合预期或缺少data对象。"
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

            log_message(f"错误: {err_msg}. 响应: {res_json}", "error")
            st.error(f"上传失败: {err_msg}")
            return None
    except requests.exceptions.HTTPError as http_err:
        err_text = http_err.response.text[:500] if hasattr(http_err,
                                                           'response') and http_err.response is not None else str(
            http_err)
        log_message(f"上传资源API HTTP错误: {http_err} - {err_text}", "error")
        status_code_err = http_err.response.status_code if hasattr(http_err,
                                                                   'response') and http_err.response is not None else 'Unknown'
        st.error(f"上传请求失败 (HTTP {status_code_err}): {err_text}")
        return None
    except Exception as e:
        log_message(f"上传资源API请求时发生意外错误: {e}", "error")
        st.error(f"上传请求时发生意外错误: {e}")
        return None


# --- Video Avatar (for video) & Voice Functions ---
def upload_photo_avatar(api_key, image_path, avatar_name="My Custom Avatar"):
    if not os.path.exists(image_path): log_message(f"错误: 视频头像图片文件未找到: {image_path}", "error"); return None
    url = f"{get_api_urls('v2')}/avatar/create_photo_avatar"
    log_message(f"正在上传照片以创建视频 Avatar: {avatar_name} 从 {image_path}")
    files = {'photo': (os.path.basename(image_path), open(image_path, 'rb'))};
    data = {'name': avatar_name}
    try:
        response = requests.post(url, headers=get_headers(api_key, content_type=None), files=files, data=data)
        response.raise_for_status();
        res_json = response.json()
        if res_json.get("data", {}).get("avatar_id"):  # Added default {} for .get("data")
            log_message(f"照片视频 Avatar 创建成功，ID: {res_json['data']['avatar_id']}", "success");
            return res_json["data"]["avatar_id"]
        else:
            log_message(f"错误: {res_json.get('error', {}).get('message', '响应中未找到 avatar_id')}. 详细: {res_json}",
                        "error"); return None
    except Exception as e:
        log_message(f"上传照片视频 Avatar 异常: {e}", "error"); return None
    finally:
        if 'photo' in files and files['photo'][1] and not files['photo'][1].closed: files['photo'][1].close()


def clone_voice_from_sample(api_key, audio_path, voice_name="My Cloned Voice"):
    if not os.path.exists(audio_path): log_message(f"错误: 声音样本文件未找到: {audio_path}", "error"); return None
    url = f"{get_api_urls('v1')}/voice";
    log_message(f"正在上传音频以克隆声音: {voice_name}")
    ct, _ = mimetypes.guess_type(audio_path);
    if not ct or not ct.startswith("audio/"): ct = "audio/mpeg"
    files = {'files': (os.path.basename(audio_path), open(audio_path, 'rb'), ct)};
    data = {'name': voice_name}
    try:
        response = requests.post(url, headers=get_headers(api_key, content_type=None), files=files, data=data)
        response.raise_for_status();
        res_json = response.json()
        if res_json.get("data", {}).get("voice_id"):
            log_message(f"声音克隆成功，Voice ID: {res_json['data']['voice_id']}", "success");
            return res_json['data']['voice_id']
        else:
            log_message(f"错误: {res_json.get('error', {}).get('message', '响应中未找到 voice_id')}. 详细:{res_json}",
                        "error"); return None
    except Exception as e:
        log_message(f"克隆声音失败: {e}", "error"); return None
    finally:
        if 'files' in files and files['files'][1] and not files['files'][1].closed: files['files'][1].close()


# --- Video Generation (using Talking Photo or Standard Avatar) ---
def generate_video_with_photo_or_avatar(api_key, text_script, voice_id, title, test_mode, add_caption, dimension_preset,
                                        talking_photo_id=None, avatar_id=None):
    if not (talking_photo_id or avatar_id): log_message("错误: 必须提供 talking_photo_id 或 avatar_id 来生成视频。",
                                                        "error"); return None
    if not voice_id: log_message("错误: 必须提供 voice_id 来生成视频。", "error"); return None
    url = f"{get_api_urls('v2')}/video/generate"
    char_payload = {"type": "talking_photo" if talking_photo_id else "avatar",
                    ("talking_photo_id" if talking_photo_id else "avatar_id"): (
                        talking_photo_id if talking_photo_id else avatar_id)}
    log_message(
        f"使用 {'Talking Photo ID ' + talking_photo_id if talking_photo_id else 'Avatar ID ' + avatar_id} 生成视频...")
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
            dim = {"width": 1920, "height": 1080}; log_message("警告: 视频尺寸无效, 使用16:9", "warning")
    payload = {"video_inputs": video_inputs, "test": test_mode, "caption": add_caption, "dimension": dim,
               "title": title}
    print(payload)
    log_message(f"发送视频生成请求 (角色类型: {char_payload['type']})...");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()
        if data.get("data", {}).get("video_id"):
            return data["data"]["video_id"]
        else:
            log_message(f"错误: {data.get('error', {}).get('message', '响应中未找到 video_id')}. 详细:{data}",
                        "error"); return None
    except Exception as e:
        log_message(f"生成视频请求失败: {e}", "error"); return None


def check_heygen_video_status(api_key, video_id):  # Used for any video generation status
    url = f"{get_api_urls('v1')}/video_status.get?video_id={video_id}"
    try:
        response = requests.get(url, headers=get_headers(api_key, "accept_json"))
        response.raise_for_status();
        data = response.json()
        if data.get("data"):
            return data["data"].get("status"), data["data"].get("video_url"), data["data"].get("error")
        else:
            log_message(f"错误：视频状态响应格式不符. 响应: {data}", "error"); return "error", None, {
                "message": "响应格式错误"}
    except Exception as e:
        log_message(f"检查视频状态失败 (ID: {video_id}): {e}", "error"); return "error", None, {"message": str(e)}


# --- Photo Avatar Group Management Functions ---
def create_photo_avatar_group(api_key, name, key):
    url = f"{get_api_urls('v2')}/photo_avatar/avatar_group/create";
    payload = {"name": name, "image_key": key}
    log_message(f"创建头像组 '{name}' using key '{key}'");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()
        if data.get("data", {}).get("group_id"):
            log_message(f"组'{name}'创建成功, ID: {data['data']['group_id']}", "success");
            return data['data']['group_id']
        else:
            log_message(f"创建组错误: {data.get('error', {}).get('message', '未知')}. 详细:{data}",
                        "error"); return None
    except Exception as e:
        log_message(f"创建组API失败: {e}", "error"); return None


def add_looks_to_avatar_group(api_key, group_id, keys, name="look_collection"):
    url = f"{get_api_urls('v2')}/photo_avatar/avatar_group/add";
    payload = {"group_id": group_id, "image_keys": keys, "name": name}
    log_message(f"向组{group_id}添加{len(keys)}Looks (collection:{name})");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()  # API doc unclear on success response structure
        if response.ok and (not data or not data.get("error")):  # Assume success if ok and no error field
            log_message(f"Looks成功添加到组{group_id}", "success");
            return True
        else:
            log_message(f"添加Looks到组{group_id}失败: {data.get('error', {}).get('message', '未知')}. 详细:{data}",
                        "error"); return False
    except Exception as e:
        log_message(f"添加Looks API失败: {e}", "error"); return False


def train_photo_avatar_group(api_key, group_id):
    url = f"{get_api_urls('v2')}/photo_avatar/train";
    payload = {"group_id": group_id}
    log_message(f"训练头像组: {group_id}");
    try:
        response = requests.post(url, headers=get_headers(api_key, "json"), json=payload)
        response.raise_for_status();
        data = response.json()
        if response.ok:
            tid = data.get("data", {}).get("job_id") or data.get("data", {}).get("training_id") or group_id
            log_message(f"组训练已提交. GroupID:{group_id}, TrackID:{tid}", "success");
            return tid
        else:
            log_message(f"训练组错误: {data.get('error', {}).get('message', '未知')}. 详细:{data}",
                        "error"); return None
    except Exception as e:
        log_message(f"训练组API失败: {e}", "error"); return None


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
        if not status and err_msg: log_message(f"组训练状态API错误(ID:{training_id}):{err_msg}",
                                               "error"); return "error", {"message": err_msg}
        return status, {"message": err_msg} if err_msg else None  # error_msg is None on success
    except Exception as e:
        log_message(f"检查组训练状态API失败(ID:{training_id}):{e}", "error"); return "error", {"message": str(e)}


def list_avatar_groups(api_key):
    url = f"{get_api_urls('v2')}/avatar_group.list";
    log_message(f"请求头像组列表...");
    try:
        response = requests.get(url, headers=get_headers(api_key, "accept_json"))
        response.raise_for_status();
        data = response.json()
        groups = data.get("data", {}).get("list", [])
        if not groups and isinstance(data.get("data"), list): groups = data.get("data")
        if groups is not None:
            log_message(f"成功获取{len(groups)}个头像组", "success")  # groups can be an empty list
        elif data.get("error"):
            log_message(f"获取组列表API错误:{data.get('error', {}).get('message', '未知')}", "error")
        else:
            log_message("获取组列表响应格式未知", "info")
        return groups if groups is not None else []  # Ensure return list
    except Exception as e:
        log_message(f"获取组列表API失败:{e}", "error"); return []


def list_avatar_group_looks(api_key, group_id):
    url = f"{get_api_urls('v2')}/avatar_group/{group_id}/avatars";
    log_message(f"请求组'{group_id}'的Looks列表...");
    try:
        response = requests.get(url, headers=get_headers(api_key, "accept_json"))
        response.raise_for_status();
        data = response.json()

        looks = data['data'].get("avatar_list", [])
        if looks is not None:
            log_message(f"成功获取组'{group_id}'的{len(looks)}个Looks", "success")
        elif data.get("error"):
            log_message(f"获取组'{group_id}'Looks时API错误:{data.get('error', {}).get('message', '未知')}", "error")
        else:
            log_message(f"获取组'{group_id}'Looks列表响应格式未知", "info")
        return looks if looks is not None else []
    except Exception as e:
        log_message(f"获取组'{group_id}'Looks API失败:{e}", "error"); return []


# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="HeyGen Photo Avatar Video Creator")
st.title("🎬 HeyGen 照片头像视频创作工具")

# Initialize session state variables
default_api_key = "Y2JiMmYyZThlMzEwNDk3MGJhOTlhNDc1YWEwNGM5YTQtMTc0NzM3MTgwOA=="
for key, default_val in {
    "api_key": default_api_key, "logs": [],
    "video_id": None, "video_url": None, "video_status": None,
    "voice_id_to_use_for_video": st.session_state.get("ui_vid_voice_id_exist", "0093c2419a354e9995106a61791827ba"),
    # Initialize from UI default
    "avatar_groups_list_for_vid": [], "selected_group_id_for_vid_looks": None,
    "group_looks_list_for_vid": [], "selected_talking_photo_id_for_vid": None,
    "group_id": None, "group_id_after_creation_flag": False, "current_group_name": None,
    "group_training_id": None, "group_training_status": None,
    "temp_initial_image_key_group_ui": None, "temp_look_image_keys_group_ui": [],
    "add_looks_status_msg_ui": None,
    "processing_type": None, "current_step": "idle",
    "last_displayed_log_count": 0,
    # UI input states
    "ui_grp_new_name": "", "ui_grp_initial_img_option": "输入 Image Key", "ui_grp_initial_img_key_direct": "",
    "ui_grp_addlooks_groupid": "", "ui_grp_addlooks_name": "additional_looks", "ui_grp_addlooks_keys_text": "",
    "ui_grp_train_groupid": "",
    "ui_vid_script": "你好，欢迎使用HeyGen照片头像视频功能！", "ui_vid_title": "我的头像组视频",
    "ui_vid_test_mode": True, "ui_vid_add_captions": True, "ui_vid_dimension": "16:9",
    "ui_vid_voice_option": "使用现有 Voice ID", "ui_vid_voice_id_exist": "d7bbcdd6964c47bdaae26decade4a933",
    "ui_vid_voice_name_new": "MyClonedVidVoice",
    "ui_vid_groupid_for_look_select": ""
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_val

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ API 设置")
    is_processing_main_ui_app = (st.session_state.current_step != "idle")
    st.session_state.api_key = st.text_input("HeyGen API Key", value=st.session_state.api_key, type="password",
                                             disabled=is_processing_main_ui_app,
                                             key="api_key_input_sidebar_final_app_main_key_v2")

    st.header("🛠️ 选择操作")
    operation_type_main_ui_app = st.radio(
        "您想做什么?",
        ("管理照片头像组", "生成视频 (使用照片头像组的Look)"),
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
if operation_type_main_ui_app == "管理照片头像组":
    st.header("🖼️ 照片头像组管理")
    st.caption("步骤 1 & 2: 创建组并添加图片。步骤 3: 训练组以获得更好的一致性。")

    if st.session_state.group_id:
        st.success(
            f"当前操作的 Group ID: **{st.session_state.group_id}** (组名: {st.session_state.current_group_name or '未命名'})")
    if st.session_state.group_training_status and st.session_state.group_training_status != "Ready" and st.session_state.current_step == "idle" and st.session_state.group_id:
        st.warning(f"组 {st.session_state.group_id} 的训练状态为: {st.session_state.group_training_status}.")

    group_action_main_ui_val = st.selectbox(
        "选择组管理操作:",
        ["(选择操作)", "1. 创建新头像组", "2. 向组中添加图片(Looks)", "3. 训练头像组"],
        key="group_action_choice_main_app_key_v2",
        disabled=is_processing_main_ui_app
    )

    if group_action_main_ui_val == "1. 创建新头像组":
        st.subheader("1. 创建新照片头像组")
        st.session_state.ui_grp_new_name = st.text_input("新组名:", value=st.session_state.ui_grp_new_name,
                                                         key="ui_grp_new_name_key_v2",
                                                         disabled=is_processing_main_ui_app)
        st.markdown("**初始图片 (用于创建组):**")
        st.session_state.ui_grp_initial_img_option = st.radio("初始图片来源:", ("输入 Image Key", "上传图片"),
                                                              key="ui_grp_initial_img_option_key_v2",
                                                              index=["输入 Image Key", "上传图片"].index(
                                                                  st.session_state.ui_grp_initial_img_option),
                                                              horizontal=True, disabled=is_processing_main_ui_app)
        initial_image_key_for_creation_val_ui = ""
        if st.session_state.ui_grp_initial_img_option == "输入 Image Key":
            st.session_state.ui_grp_initial_img_key_direct = st.text_input("初始图片的 Image Key:",
                                                                           value=st.session_state.ui_grp_initial_img_key_direct,
                                                                           placeholder="例如: image/xxxx/original",
                                                                           key="ui_grp_initial_img_key_direct_key_v2",
                                                                           disabled=is_processing_main_ui_app)
            initial_image_key_for_creation_val_ui = st.session_state.ui_grp_initial_img_key_direct
        elif st.session_state.ui_grp_initial_img_option == "上传图片":
            uploaded_initial_img_grp_main_ui_val = st.file_uploader("上传初始图片:", type=["jpg", "png", "jpeg"],
                                                                    key="ui_grp_initial_img_uploader_key_v2",
                                                                    disabled=is_processing_main_ui_app)
            if uploaded_initial_img_grp_main_ui_val:
                if st.button("上传并获取Key (初始图片)", key="ui_grp_upload_initial_btn_key_v2",
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

        if st.button("➡️ 创建头像组", key="ui_grp_create_btn_key_v2",
                     disabled=is_processing_main_ui_app or not st.session_state.ui_grp_new_name or not initial_image_key_for_creation_val_ui):
            st.session_state.processing_type = "avatar_group_manage";
            st.session_state.current_step = "group_create"
            st.session_state.current_group_name_for_creation = st.session_state.ui_grp_new_name
            st.session_state.current_initial_image_key_for_creation = initial_image_key_for_creation_val_ui
            for key_to_reset in ["group_id", "group_id_after_creation_flag", "group_training_id",
                                 "group_training_status", "current_group_name", "add_looks_status_msg_ui"]:
                st.session_state[key_to_reset] = False if key_to_reset == "group_id_after_creation_flag" else None
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0
            log_message(f"开始创建照片头像组 '{st.session_state.ui_grp_new_name}'...")
            st.rerun()

    elif group_action_main_ui_val == "2. 向组中添加图片(Looks)":
        st.subheader("2. 向组中添加图片(Looks)")
        st.session_state.ui_grp_addlooks_groupid = st.text_input("目标 Group ID:",
                                                                 value=st.session_state.ui_grp_addlooks_groupid or st.session_state.get(
                                                                     "group_id", ""),
                                                                 key="ui_grp_addlooks_groupid_key_v2",
                                                                 disabled=is_processing_main_ui_app)
        st.session_state.ui_grp_addlooks_name = st.text_input("这批Looks的名称/描述 (可选):",
                                                              value=st.session_state.ui_grp_addlooks_name,
                                                              key="ui_grp_addlooks_name_key_v2",
                                                              disabled=is_processing_main_ui_app)
        st.markdown("**要添加的图片 (提供 Image Keys):** (每行一个)")
        st.session_state.ui_grp_addlooks_keys_text = st.text_area("Image Keys:",
                                                                  value=st.session_state.ui_grp_addlooks_keys_text,
                                                                  placeholder="image/key1/original\nimage/key2/original",
                                                                  height=100, key="ui_grp_addlooks_keys_text_key_v2",
                                                                  disabled=is_processing_main_ui_app)
        st.markdown("或者 **上传图片 (获取 Keys):**")
        uploaded_looks_add_grp_main_ui_val = st.file_uploader("上传一张或多张图片作为Looks:",
                                                              type=["jpg", "png", "jpeg"], accept_multiple_files=True,
                                                              key="ui_grp_addlooks_uploader_key_v2",
                                                              disabled=is_processing_main_ui_app)
        if uploaded_looks_add_grp_main_ui_val:
            if st.button("上传选中图片并获取Keys (Looks)", key="ui_grp_addlooks_upload_btn_key_v2",
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
        if st.button("➡️ 添加 Looks 到组", key="ui_grp_addlooks_submit_btn_key_v2",
                     disabled=is_processing_main_ui_app or not st.session_state.ui_grp_addlooks_groupid or not final_keys_to_add_val):
            st.session_state.processing_type = "avatar_group_manage";
            st.session_state.current_step = "group_add_looks"
            st.session_state.current_group_id_for_add_looks = st.session_state.ui_grp_addlooks_groupid
            st.session_state.current_image_keys_for_add_looks = final_keys_to_add_val
            st.session_state.current_look_name_for_add_looks = st.session_state.ui_grp_addlooks_name
            st.session_state.add_looks_status_msg_ui = None
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0
            log_message(f"开始向组 '{st.session_state.ui_grp_addlooks_groupid}' 添加 Looks...")
            st.rerun()

    elif group_action_main_ui_val == "3. 训练头像组":
        st.subheader("3. 训练头像组")
        st.session_state.ui_grp_train_groupid = st.text_input("要训练的 Group ID:",
                                                              value=st.session_state.ui_grp_train_groupid or st.session_state.get(
                                                                  "group_id", ""), key="ui_grp_train_groupid_key_v2",
                                                              disabled=is_processing_main_ui_app)
        if st.button("➡️ 开始训练组", key="ui_grp_train_btn_key_v2",
                     disabled=is_processing_main_ui_app or not st.session_state.ui_grp_train_groupid):
            st.session_state.processing_type = "avatar_group_manage";
            st.session_state.current_step = "group_train_request"
            st.session_state.current_group_id_for_train = st.session_state.ui_grp_train_groupid
            st.session_state.group_training_id, st.session_state.group_training_status = None, "开始训练请求..."
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0
            log_message(f"开始训练照片头像组 '{st.session_state.ui_grp_train_groupid}'...")
            st.rerun()

elif operation_type_main_ui_app == "生成视频 (使用照片头像组的Look)":
    st.header("📹 使用照片头像组生成视频")
    st.session_state.ui_vid_groupid_for_look_select = st.text_input("目标头像组 Group ID:",
                                                                    value=st.session_state.ui_vid_groupid_for_look_select or st.session_state.get(
                                                                        "group_id", ""),
                                                                    key="ui_vid_groupid_for_look_select_key_v2",
                                                                    disabled=is_processing_main_ui_app)

    if st.session_state.ui_vid_groupid_for_look_select:
        if st.button("加载组内Looks", key="ui_vid_load_looks_btn_key_v2", disabled=is_processing_main_ui_app):
            st.session_state.group_looks_list_for_vid = list_avatar_group_looks(st.session_state.api_key,
                                                                                st.session_state.ui_vid_groupid_for_look_select)
            if not st.session_state.group_looks_list_for_vid: st.warning("未找到Looks或加载失败。")
            st.session_state.selected_talking_photo_id_for_vid = None  # Reset selected look
            st.rerun()

        if st.session_state.group_looks_list_for_vid:
            look_options_for_vid_val = {}
            for i, look_data in enumerate(st.session_state.group_looks_list_for_vid):
                tp_id = look_data.get("talking_photo_id") or look_data.get("id") or look_data.get(
                    "image_key")  # IMPORTANT: Confirm this mapping
                look_name = look_data.get("name", f"Look {i + 1}") + (f" (ID: ...{tp_id[-6:]})" if tp_id else "")
                if tp_id: look_options_for_vid_val[tp_id] = look_name

            if look_options_for_vid_val:
                # If a look was previously selected and still valid, keep it, else None
                current_selection_vid_look = st.session_state.selected_talking_photo_id_for_vid
                if current_selection_vid_look not in look_options_for_vid_val: current_selection_vid_look = None

                st.session_state.selected_talking_photo_id_for_vid = st.selectbox(
                    "选择一个Look作为视频角色:", options=list(look_options_for_vid_val.keys()),
                    format_func=lambda x: look_options_for_vid_val.get(x, x),
                    index=list(look_options_for_vid_val.keys()).index(
                        current_selection_vid_look) if current_selection_vid_look else 0,  # Try to preserve selection
                    key="ui_vid_select_talking_photo_key_v2", disabled=is_processing_main_ui_app,
                    placeholder="选择一个照片头像..."
                )
            else:
                st.write("此组没有可用的Looks或它们的ID无法解析为Talking Photo ID。")
        elif st.session_state.ui_vid_groupid_for_look_select:
            st.write("点击“加载组内Looks”以选择。")

    with st.expander("语音设置 (视频)", expanded=True):
        st.session_state.ui_vid_voice_option = st.radio("选择 Voice 来源:", ("克隆新声音", "使用现有 Voice ID"),
                                                        key="ui_vid_voice_option_grp_vid_key_v2",
                                                        index=["克隆新声音", "使用现有 Voice ID"].index(
                                                            st.session_state.ui_vid_voice_option),
                                                        disabled=is_processing_main_ui_app)
        if st.session_state.ui_vid_voice_option == "克隆新声音":
            uploaded_voice_sample_grp_vid_ui_val = st.file_uploader("上传声音样本", type=["mp3", "wav"],
                                                                    key="ui_vid_voice_uploader_grp_vid_key_v2",
                                                                    disabled=is_processing_main_ui_app)
            st.session_state.ui_vid_voice_name_new = st.text_input("新 Voice 名称",
                                                                   value=st.session_state.ui_vid_voice_name_new,
                                                                   key="ui_vid_voice_name_new_grp_vid_key_v2",
                                                                   disabled=is_processing_main_ui_app)
        else:
            st.session_state.ui_vid_voice_id_exist = st.text_input("现有 Voice ID",
                                                                   value=st.session_state.ui_vid_voice_id_exist,
                                                                   key="ui_vid_voice_id_exist_grp_vid_key_v2",
                                                                   disabled=is_processing_main_ui_app)

    st.subheader("📝 视频内容和参数")
    st.session_state.ui_vid_script = st.text_area("视频脚本", value=st.session_state.ui_vid_script,
                                                  key="ui_vid_script_grp_vid_key_v2",
                                                  disabled=is_processing_main_ui_app)
    st.session_state.ui_vid_title = st.text_input("视频标题", value=st.session_state.ui_vid_title,
                                                  key="ui_vid_title_grp_vid_key_v2", disabled=is_processing_main_ui_app)
    c1_grp_vid_val, c2_grp_vid_val, c3_grp_vid_val = st.columns(3)
    dimension_options_grp_vid_val = ["16:9", "9:16", "1:1", "4:5", "1280x720", "1920x1080"]
    st.session_state.ui_vid_test_mode = c1_grp_vid_val.checkbox("测试模式", value=st.session_state.ui_vid_test_mode,
                                                                key="ui_vid_test_mode_grp_vid_key_v2",
                                                                disabled=is_processing_main_ui_app)
    st.session_state.ui_vid_add_captions = c2_grp_vid_val.checkbox("添加字幕",
                                                                   value=st.session_state.ui_vid_add_captions,
                                                                   key="ui_vid_add_captions_grp_vid_key_v2",
                                                                   disabled=is_processing_main_ui_app)
    st.session_state.ui_vid_dimension = c3_grp_vid_val.selectbox("视频尺寸", dimension_options_grp_vid_val,
                                                                 index=dimension_options_grp_vid_val.index(
                                                                     st.session_state.ui_vid_dimension) if st.session_state.ui_vid_dimension in dimension_options_grp_vid_val else 0,
                                                                 key="ui_vid_dimension_grp_vid_key_v2",
                                                                 disabled=is_processing_main_ui_app)

    st.markdown("---")
    if st.button("🚀 生成头像组视频",
                 disabled=is_processing_main_ui_app or not st.session_state.selected_talking_photo_id_for_vid,
                 key="ui_vid_generate_grp_vid_btn_key_v2"):
        if not st.session_state.api_key.strip():
            st.error("API Key缺失!")
        elif not st.session_state.ui_vid_script.strip():
            st.error("视频脚本缺失!")
        else:
            st.session_state.processing_type = "video_from_group_look"
            st.session_state.current_step = "video_from_group_get_voice_id"
            for key_to_reset in ["video_id", "video_url", "voice_id_to_use_for_video"]: st.session_state[
                key_to_reset] = None
            st.session_state.video_status = "开始视频处理 (头像组)..."
            st.session_state.logs, st.session_state.last_displayed_log_count = [], 0

            # Store uploaded voice file bytes if clone option is selected
            if st.session_state.ui_vid_voice_option == "克隆新声音" and uploaded_voice_sample_grp_vid_ui_val is not None:
                st.session_state.temp_uploaded_voice_bytes_for_grp_vid = uploaded_voice_sample_grp_vid_ui_val.getvalue()
                st.session_state.temp_uploaded_voice_filename_for_grp_vid = uploaded_voice_sample_grp_vid_ui_val.name
            else:
                st.session_state.temp_uploaded_voice_bytes_for_grp_vid = None
                st.session_state.temp_uploaded_voice_filename_for_grp_vid = None

            log_message("开始使用头像组Look生成视频流程...")
            st.rerun()

# --- Processing Logic ---
if st.session_state.current_step != "idle":
    with status_placeholder_main_ui_app.container():
        # ... (Your existing status display logic, ensure it correctly uses session state vars) ...
        pass  # Placeholder, use your detailed status display logic from previous full code

    # --- Video (from Group Look) Processing Steps ---
    if st.session_state.processing_type == "video_from_group_look":
        if st.session_state.current_step == "video_from_group_get_voice_id":
            log_message("视频(头像组)步骤1: 确定Voice ID...")
            voice_id_to_set_for_grp_vid = None
            if st.session_state.ui_vid_voice_option == "克隆新声音":
                if st.session_state.get("temp_uploaded_voice_bytes_for_grp_vid"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=
                    os.path.splitext(st.session_state.temp_uploaded_voice_filename_for_grp_vid)[1]) as tmp_f:
                        tmp_f.write(st.session_state.temp_uploaded_voice_bytes_for_grp_vid);
                        temp_path = tmp_f.name
                    voice_name = st.session_state.ui_vid_voice_name_new or "GrpVidClonedVoice"
                    voice_id_to_set_for_grp_vid = clone_voice_from_sample(st.session_state.api_key, temp_path,
                                                                          voice_name)
                    os.unlink(temp_path);
                    if voice_id_to_set_for_grp_vid: time.sleep(10)  # Allow time for voice to be usable
                    st.session_state.temp_uploaded_voice_bytes_for_grp_vid = None  # Clean up
                    st.session_state.temp_uploaded_voice_filename_for_grp_vid = None
                else:
                    log_message("警告: 未能处理上传的Voice样本文件 (头像组视频)。", "warning")
            else:
                voice_id_to_set_for_grp_vid = st.session_state.ui_vid_voice_id_exist

            st.session_state.voice_id_to_use_for_video = voice_id_to_set_for_grp_vid
            if not st.session_state.voice_id_to_use_for_video:
                log_message("错误: 未能确定Voice ID (头像组视频)。", "error"); st.session_state.current_step = "idle"
            else:
                log_message(
                    f"使用Voice ID: {st.session_state.voice_id_to_use_for_video} (头像组视频)"); st.session_state.current_step = "video_from_group_generate_request"
            st.rerun()

        elif st.session_state.current_step == "video_from_group_generate_request":
            log_message("视频(头像组)步骤2: 提交视频生成请求...")
            if not st.session_state.selected_talking_photo_id_for_vid or not st.session_state.voice_id_to_use_for_video:
                log_message("错误: 缺少Talking Photo ID 或 Voice ID (头像组视频)。", "error");
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
                    st.session_state.video_status = "视频(头像组)已提交..."
                    log_message(f"视频(头像组)请求已提交，ID: {video_id_res_grp_vid}");
                    st.session_state.current_step = "video_from_group_poll_status"
                else:
                    st.session_state.video_status = "视频(头像组)请求失败。"; st.session_state.current_step = "idle"
            st.rerun()

        elif st.session_state.current_step == "video_from_group_poll_status" and st.session_state.video_id:
            status_grp_vid, url_grp_vid, err_grp_vid = check_heygen_video_status(st.session_state.api_key,
                                                                                 st.session_state.video_id)
            is_final_grp_vid = False
            if status_grp_vid == "completed":
                st.session_state.video_url = url_grp_vid; log_message(f"视频(头像组)生成完成! URL: {url_grp_vid}",
                                                                      "success"); st.session_state.current_step = "idle"; is_final_grp_vid = True
            elif status_grp_vid == "failed":
                msg_grp_vid = err_grp_vid.get('message', '未知') if isinstance(err_grp_vid, dict) else str(
                    err_grp_vid); log_message(f"视频(头像组)生成失败: {msg_grp_vid}",
                                              "error"); st.session_state.current_step = "idle"; is_final_grp_vid = True
            elif status_grp_vid == "error":
                msg_grp_vid = err_grp_vid.get('message', 'API调用错') if isinstance(err_grp_vid, dict) else str(
                    err_grp_vid); log_message(f"检查视频(头像组)状态出错: {status_grp_vid}, {msg_grp_vid}",
                                              "error"); st.session_state.current_step = "idle"; is_final_grp_vid = True
            st.session_state.video_status = status_grp_vid
            if is_final_grp_vid:
                st.rerun()
            else:
                log_message(f"轮询视频(头像组)状态: {status_grp_vid}"); time.sleep(10); st.rerun()

    # --- Avatar Group Management Processing Steps ---
    elif st.session_state.processing_type == "avatar_group_manage":
        # ... (Processing logic for group_create, group_add_looks, group_train_request, group_poll_train_status)
        # This logic should be similar to the last complete code you had for these steps,
        # ensuring it uses st.session_state variables that were set by the UI button clicks.
        if st.session_state.current_step == "group_create":
            log_message(f"处理中：创建组 '{st.session_state.current_group_name_for_creation}'...")
            group_id_res_grp_proc_val_logic_final_val_manage = create_photo_avatar_group(st.session_state.api_key,
                                                                                         st.session_state.current_group_name_for_creation,
                                                                                         st.session_state.current_initial_image_key_for_creation)
            if group_id_res_grp_proc_val_logic_final_val_manage:
                st.session_state.group_id = group_id_res_grp_proc_val_logic_final_val_manage
                st.session_state.group_id_after_creation_flag = True
                st.session_state.current_group_name = st.session_state.current_group_name_for_creation
                log_message(
                    f"组 '{st.session_state.current_group_name}' 创建成功，ID: {group_id_res_grp_proc_val_logic_final_val_manage}",
                    "success")
            else:
                log_message(f"创建组 '{st.session_state.current_group_name_for_creation}' 失败。", "error")
            st.session_state.current_step = "idle"
            st.session_state.temp_initial_image_key_group_ui = None
            st.rerun()

        elif st.session_state.current_step == "group_add_looks":
            log_message(f"处理中：向组 '{st.session_state.current_group_id_for_add_looks}' 添加 Looks...")
            success_add_looks_val_proc_val_logic_final_val_manage = add_looks_to_avatar_group(st.session_state.api_key,
                                                                                              st.session_state.current_group_id_for_add_looks,
                                                                                              st.session_state.current_image_keys_for_add_looks,
                                                                                              st.session_state.current_look_name_for_add_looks)
            if success_add_looks_val_proc_val_logic_final_val_manage:
                st.session_state.add_looks_status_msg_ui = f"Looks 成功添加到组 '{st.session_state.current_group_id_for_add_looks}'."
            else:
                st.session_state.add_looks_status_msg_ui = f"向组 '{st.session_state.current_group_id_for_add_looks}' 添加 Looks 失败。"
            st.session_state.current_step = "group_add_looks_status"
            st.session_state.temp_look_image_keys_group_ui = []
            st.rerun()

        elif st.session_state.current_step == "group_add_looks_status":
            pass

        elif st.session_state.current_step == "group_train_request":
            log_message(f"处理中：为组 '{st.session_state.current_group_id_for_train}' 发起训练...")
            training_id_val_grp_proc_val_logic_final_val_manage = train_photo_avatar_group(st.session_state.api_key,
                                                                                           st.session_state.current_group_id_for_train)
            if training_id_val_grp_proc_val_logic_final_val_manage:
                st.session_state.group_training_id = training_id_val_grp_proc_val_logic_final_val_manage
                st.session_state.group_training_status = "训练已提交，等待处理..."
                log_message(f"组训练已提交/启动. Tracking ID: {training_id_val_grp_proc_val_logic_final_val_manage}")
                st.session_state.current_step = "group_poll_train_status"
            else:
                log_message(f"为组 '{st.session_state.current_group_id_for_train}' 发起训练失败。", "error")
                st.session_state.group_training_status = "训练发起失败";
                st.session_state.current_step = "idle"
            st.rerun()

        elif st.session_state.current_step == "group_poll_train_status" and st.session_state.group_training_id:
            status_train_poll_grp_proc_val_logic_final_val_manage, err_info_train_poll_grp_proc_val_logic_final_val_manage = check_photo_avatar_group_training_status(
                st.session_state.api_key, st.session_state.group_training_id)
            is_final_train_poll_grp_proc_val_logic_final_val_manage = False
            # API Doc states: "Pending", "Training", "Ready" as statuses
            if status_train_poll_grp_proc_val_logic_final_val_manage == "Ready":
                log_message(f"头像组 (ID: {st.session_state.group_training_id}) 训练完成!", "success");
                st.session_state.current_step = "idle";
                is_final_train_poll_grp_proc_val_logic_final_val_manage = True
            elif status_train_poll_grp_proc_val_logic_final_val_manage == "Failed" or status_train_poll_grp_proc_val_logic_final_val_manage == "Error":
                err_train_poll_grp_msg_proc_val_logic_final_val_manage = err_info_train_poll_grp_proc_val_logic_final_val_manage.get(
                    "message", "未知训练错误") if isinstance(err_info_train_poll_grp_proc_val_logic_final_val_manage,
                                                             dict) else str(
                    err_info_train_poll_grp_proc_val_logic_final_val_manage)
                log_message(
                    f"头像组 (ID: {st.session_state.group_training_id}) 训练失败. 原因: {err_train_poll_grp_msg_proc_val_logic_final_val_manage}",
                    "error");
                st.session_state.current_step = "idle";
                is_final_train_poll_grp_proc_val_logic_final_val_manage = True

            st.session_state.group_training_status = status_train_poll_grp_proc_val_logic_final_val_manage
            if is_final_train_poll_grp_proc_val_logic_final_val_manage:
                st.rerun()
            elif status_train_poll_grp_proc_val_logic_final_val_manage in ["Pending", "Training"]:
                log_message(
                    f"轮询头像组训练状态 (ID: {st.session_state.group_training_id}): {status_train_poll_grp_proc_val_logic_final_val_manage}");
                time.sleep(10);
                st.rerun()
            else:
                log_message(
                    f"收到未知的训练状态 '{status_train_poll_grp_proc_val_logic_final_val_manage}' 或检查时出错 (ID: {st.session_state.group_training_id})",
                    "warning")
                st.session_state.current_step = "idle";
                st.rerun()

    # Removed single AI photo generation processing logic for simplification, can be added back if needed

# --- Final Log Display ---
if st.session_state.logs:
    display_logs_main_ui_app_final()