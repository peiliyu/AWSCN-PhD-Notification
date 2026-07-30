import json
import os
import logging
import lark_oapi as lark
from lark_oapi.api.im.v1 import *

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

APP_ID = os.environ["APP_ID"]
APP_SECRET = os.environ["APP_SECRET"]
RECEIVE_USER_ID = os.environ["RECEIVE_USER_ID"]
CHAT_ID = os.environ["CHAT_ID"]
ENABLE_APP_URGENT = os.environ.get("ENABLE_APP_URGENT", "true").lower() == "true"
ENABLE_SMS_URGENT = os.environ.get("ENABLE_SMS_URGENT", "false").lower() == "true"
ENABLE_PHONE_URGENT = os.environ.get("ENABLE_PHONE_URGENT", "false").lower() == "true"

_client = None

def get_client():
    global _client
    if _client is None:
        lark_log_level = getattr(lark.LogLevel, os.environ.get("LARK_LOG_LEVEL", "INFO"), lark.LogLevel.INFO)
        _client = lark.Client.builder() \
            .app_id(APP_ID) \
            .app_secret(APP_SECRET) \
            .log_level(lark_log_level) \
            .build()
    return _client


def lambda_handler(event, context):
    message_content = event if isinstance(event, str) else json.dumps(event, indent=2, ensure_ascii=False)
    logger.info("收到事件, 消息长度: %d", len(message_content))

    client = get_client()

    # 1. 发送消息到群
    send_resp = client.im.v1.message.create(
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(CreateMessageRequestBody.builder()
            .receive_id(CHAT_ID)
            .msg_type("text")
            .content(json.dumps({"text": message_content}))
            .build())
        .build()
    )
    if not send_resp.success():
        err = f"发送消息失败, code: {send_resp.code}, msg: {send_resp.msg}, log_id: {send_resp.get_log_id()}"
        logger.error(err)
        return {"statusCode": 500, "body": err}

    message_id = send_resp.data.message_id
    logger.info("消息发送成功, message_id: %s", message_id)

    urgent_receivers = UrgentReceivers.builder().user_id_list([RECEIVE_USER_ID]).build()

    # 2. 应用内加急
    if ENABLE_APP_URGENT:
        resp = client.im.v1.message.urgent_app(
            UrgentAppMessageRequest.builder()
            .message_id(message_id).user_id_type("user_id")
            .request_body(urgent_receivers).build()
        )
        if not resp.success():
            err = f"应用内加急失败, code: {resp.code}, msg: {resp.msg}, log_id: {resp.get_log_id()}"
            logger.error(err)
            return {"statusCode": 500, "body": err}
        logger.info("应用内加急成功")

    # 3. 短信加急
    if ENABLE_SMS_URGENT:
        resp = client.im.v1.message.urgent_sms(
            UrgentSmsMessageRequest.builder()
            .message_id(message_id).user_id_type("user_id")
            .request_body(urgent_receivers).build()
        )
        if not resp.success():
            err = f"短信加急失败, code: {resp.code}, msg: {resp.msg}, log_id: {resp.get_log_id()}"
            logger.error(err)
            return {"statusCode": 500, "body": err}
        logger.info("短信加急成功")

    # 4. 电话加急
    if ENABLE_PHONE_URGENT:
        resp = client.im.v1.message.urgent_phone(
            UrgentPhoneMessageRequest.builder()
            .message_id(message_id).user_id_type("user_id")
            .request_body(urgent_receivers).build()
        )
        if not resp.success():
            err = f"电话加急失败, code: {resp.code}, msg: {resp.msg}, log_id: {resp.get_log_id()}"
            logger.error(err)
            return {"statusCode": 500, "body": err}
        logger.info("电话加急成功")

    return {"statusCode": 200, "body": f"消息发送并加急成功, message_id: {message_id}"}
