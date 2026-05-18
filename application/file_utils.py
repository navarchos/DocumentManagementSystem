from io import BytesIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app, send_file


ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'jpg', 'png', 'zip'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_s3_storage_enabled():
    return all([
        current_app.config.get('S3_BUCKET_NAME'),
        current_app.config.get('S3_ACCESS_KEY_ID'),
        current_app.config.get('S3_SECRET_ACCESS_KEY'),
    ])


def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=current_app.config['S3_ENDPOINT_URL'],
        region_name=current_app.config['S3_REGION'],
        aws_access_key_id=current_app.config['S3_ACCESS_KEY_ID'],
        aws_secret_access_key=current_app.config['S3_SECRET_ACCESS_KEY'],
    )


def build_storage_path(order_id, filename):
    return f'orders/{order_id}/{filename}'


def is_s3_storage_path(storage_path):
    return storage_path.startswith('orders/')


def save_order_file(file, storage_path):
    if not is_s3_storage_enabled():
        raise RuntimeError('S3 storage is not configured')

    try:
        get_s3_client().upload_fileobj(
            file,
            current_app.config['S3_BUCKET_NAME'],
            storage_path,
            ExtraArgs={'ContentType': file.mimetype or 'application/octet-stream'},
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError('Could not upload file to S3 storage') from exc


def send_order_file(order_file):
    if is_s3_storage_enabled() and is_s3_storage_path(order_file.filepath):
        try:
            response = get_s3_client().get_object(
                Bucket=current_app.config['S3_BUCKET_NAME'],
                Key=order_file.filepath,
            )
        except (BotoCoreError, ClientError) as exc:
            raise FileNotFoundError('File not found in S3 storage') from exc

        file_stream = BytesIO(response['Body'].read())
        file_stream.seek(0)
        return send_file(
            file_stream,
            download_name=order_file.original_name,
            as_attachment=True,
            mimetype=response.get('ContentType') or 'application/octet-stream',
        )

    return send_file(order_file.filepath, download_name=order_file.original_name, as_attachment=True)
