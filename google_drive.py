import os
import time
from datetime import datetime

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


def google_flow():
    gauth = GoogleAuth()
    # Try to load saved client credentials
    gauth.LoadCredentialsFile("mycreds.txt")
    if gauth.credentials is None:
        # Authenticate if they're not there
        # This is what solved the issues:
        gauth.GetFlow()
        gauth.flow.params.update({"access_type": "offline"})
        gauth.flow.params.update({"approval_prompt": "force"})
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        # Refresh them if expired
        gauth.Refresh()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    # Save the current credentials to a file
    gauth.SaveCredentialsFile("mycreds.txt")
    drive = GoogleDrive(gauth)
    return drive


drive = google_flow()


def upload_local_images(image_dir, esp_folder_id):
    local_files = os.listdir(image_dir)
    if local_files:
        while local_files:
            file_to_upload = local_files[0]
            file = drive.CreateFile(
                {
                    "mimeType": "image/jpeg",
                    "parents": [{"kind": "drive#fileLink", "id": esp_folder_id}],
                }
            )
            file.SetContentFile(image_dir + file_to_upload)
            file.Upload()
            os.remove(image_dir + file_to_upload)
            local_files = os.listdir(image_dir)


def get_drive_files(esp_folder_id):
    fileList = drive.ListFile(
        {"q": f"'{esp_folder_id}' in parents and trashed=false"}
    ).GetList()

    creation_dict = {}
    for file in fileList:
        creation_date = file["createdDate"]
        time_stamp = datetime.timestamp(
            datetime.strptime(creation_date, "%Y-%m-%dT%H:%M:%S.%fZ")
        )
        creation_dict[file["id"]] = time_stamp

    return creation_dict


def clean_up_drive_files(creation_dict):
    creation_dict = sorted(creation_dict.items(), key=lambda x: x[1], reverse=False)

    while len(creation_dict) > 100:
        id = creation_dict[0][0]
        file = drive.CreateFile({"id": id})
        file.Delete()
        creation_dict.pop(0)


def google_drive(image_dir, esp_folder_id):
    while True:
        try:
            print("AOL Drive...", end="\r")
            time.sleep(1)
            upload_local_images(image_dir, esp_folder_id)
            time.sleep(1)
            creation_dict = get_drive_files(esp_folder_id)
            time.sleep(1)
            clean_up_drive_files(creation_dict)
        except Exception:
            drive = google_flow()
            pass


image_dir = "/home/carmelo/Desktop/storage/images/"
esp_folder_id = "1pnkMb4-9ZMOGvagxPt7n0cJ-lhLuKZhx"
google_drive(image_dir, esp_folder_id)
