import os
import random
import re
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from typing import Optional

import jwt
import redis
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from core.dependencies import get_db, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, pwd_context, get_redis, logger
from core.models import User

router = APIRouter(prefix="/auth", tags=["用户认证"])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@router.post("/login", summary="用户登录")
def login(username: str = Body(..., description="用户名或ID"), password: str = Body(..., description="密码"),
          db: Session = Depends(get_db)):
    user = None
    hashed_password = pwd_context.hash(password)
    logger.info(f"用户登录: {username}, 密码哈希: {hashed_password}")
    if username.isdigit():
        user = db.query(User).filter(User.id == int(username)).first()
    if not user:
        user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, str(user.hashed_password)):
        raise HTTPException(status_code=400, detail="密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员解除封禁")

    # 在 token 中包含权限信息

    token_data = {"id": user.id}
    access_token = create_access_token(data=token_data,
                                       expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"status": "success", "token": access_token,
            "user": {"id": user.id, "username": user.username, "phone": user.phone, "email": user.email, "avatar": user.avatar}}


@router.post("/refresh", summary="刷新令牌")
async def refresh_token(input_data: dict = Body(...), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(input_data.get("access_token", ""), SECRET_KEY, algorithms=[ALGORITHM],
                             options={"verify_exp": False})
        user_id = payload.get("id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户无效或已被禁用")
        token_exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        if datetime.now(timezone.utc) - token_exp > timedelta(minutes=5):
            raise HTTPException(status_code=401, detail="Token 过期时间过长，请重新登录")
        new_payload = {"id": user.id}
        new_token = create_access_token(new_payload)
        return {"new_token": new_token}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="刷新令牌无效")


@router.post("/register", summary="用户注册")
def register(username: str = Body(..., description="用户名"), password: str = Body(..., description="密码"),
             factory: str = Body(..., description="工厂名称"), phone: str = Body(..., description="电话号码"),
             email: str = Body(..., description="电子邮箱"), verificationCode: str = Body(..., description="验证码"),
             db: Session = Depends(get_db), redis_client: redis.Redis = Depends(get_redis)):
    import time
    start_time = time.time()
    logger.info(f"注册开始时间: {start_time}")

    try:
        contact = phone or email
        stored_code = redis_client.get(f"verification_code:{contact}")
        if not stored_code or stored_code != verificationCode:
            raise HTTPException(status_code=400, detail="验证码无效或已过期")
        # 检查用户名是否已存在
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="用户名已存在")
        hashed_password = pwd_context.hash(password)
        new_user = User(username=username, hashed_password=hashed_password,  phone=phone, email=email, is_active=True)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        token_data = {"id": new_user.id, "role": new_user.role, "factory": new_user.factory,
                      "departments": new_user.departments}
        access_token = create_access_token(data=token_data,
                                           expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        return {"token": access_token,
                "user": {"id": new_user.id, "username": new_user.username, "factory": new_user.factory,
                         "departments": new_user.departments, "role": new_user.role, "phone": new_user.phone,
                         "email": new_user.email, "avatar": new_user.avatar}}
    except Exception as e:
        logger.error(f"注册异常: {e}")
        raise HTTPException(status_code=500, detail="注册失败")


def send_sms(phone: str, code: str):
    client = AcsClient(os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"), os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
                       "cn-hangzhou")
    request = CommonRequest()
    request.set_method("POST")
    request.set_domain("dysmsapi.aliyuncs.com")
    request.set_version("2017-05-25")
    request.set_action_name("SendSms")

    request.add_query_param("PhoneNumbers", phone)
    request.add_query_param("SignName", "你的签名名称")  # 替换为你的短信签名
    request.add_query_param("TemplateCode", "你的模板CODE")  # 替换为你的短信模板CODE
    request.add_query_param("TemplateParam", f'{{"code":"{code}"}}')

    response = client.do_action_with_exception(request)
    return response.decode("utf-8")


def send_email(to_email: str, code: str):
    smtp_server = "smtp.qq.com"  # QQ 邮箱 SMTP 服务器
    smtp_port = 465
    sender = "chensy_1213@qq.com"  # 你的 QQ 邮箱
    email_password = "afkydblqtgxjdiai"  # 替换为 QQ 邮箱生成的授权码

    subject = "验证码通知"
    content = f"您的Multi-Agent账号验证码是：{code}，有效期5分钟。"
    message = MIMEText(content, "plain", "utf-8")

    # 修正头部格式 - 使用标准格式
    message["From"] = formataddr(("多智能体协作任务系统", sender))
    message["To"] = to_email
    message["Subject"] = Header(subject, "utf-8")
    message["Message-ID"] = f"<{uuid.uuid4()}@{smtp_server.split('.')[0]}>"
    message["Date"] = formatdate(localtime=True)
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender, email_password)
        server.sendmail(sender, [to_email], message.as_string())
        server.quit()
        logger.info(f"邮件已发送至 {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"邮件发送失败: SMTP 认证失败 - {e}")
        raise HTTPException(status_code=500, detail="SMTP 认证失败，请检查邮箱授权码")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        raise HTTPException(status_code=500, detail="邮件发送失败")


@router.post("/verification", summary="发送验证码到手机或邮箱")
def send_verification_code(phone: Optional[str] = Body(None, description="电话号码"),
                           email: Optional[str] = Body(None, description="电子邮箱"),
                           redis_client: redis.Redis = Depends(get_redis)):
    if not phone and not email:
        raise HTTPException(status_code=400, detail="请提供电话号码或邮箱")
    if phone and email:
        raise HTTPException(status_code=400, detail="只能提供电话号码或邮箱中的一种")
    verification_code = str(random.randint(100000, 999999))
    target = phone or email
    redis_client.setex(f"verification_code:{target}", 300, verification_code)
    if phone:
        send_sms(phone, verification_code)
        channel = "手机"
    else:
        send_email(email, verification_code)
        channel = "邮箱"

    return {"success": True, "message": f"验证码已发送至您的{channel}", "channel": channel, "target": target}


@router.post("/forgot-password", summary="忘记密码发送验证码")
def forgot_password(text: str = Body(..., description="用户名/邮箱/手机号"), db: Session = Depends(get_db),
                    redis_client: redis.Redis = Depends(get_redis)):
    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    phone_pattern = r"^1[3-9]\d{9}$"
    if re.match(email_pattern, text):
        user = db.query(User).filter(User.email == text).first()
        if not user:
            raise HTTPException(status_code=404, detail="邮箱未注册")
        target = user.email
        channel = "邮箱"
    elif re.match(phone_pattern, text):
        user = db.query(User).filter(User.phone == text).first()
        if not user:
            raise HTTPException(status_code=404, detail="手机号未注册")
        target = user.phone
        channel = "手机"
    else:
        user = db.query(User).filter(User.username == text).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户名未注册")
        if user.email:
            target = user.email
            channel = "邮箱"
        elif user.phone:
            target = user.phone
            channel = "手机"
        else:
            raise HTTPException(status_code=400, detail="该用户未绑定邮箱或手机号")
    verification_code = str(random.randint(100000, 999999))
    redis_client.setex(f"verification_code:{target}", 300, verification_code)
    if channel == "邮箱":
        send_email(str(target), verification_code)
    else:
        send_sms(str(target), verification_code)
    return {"success": True, "message": f"验证码已发送至您的{channel}", "channel": channel, "target": target}
