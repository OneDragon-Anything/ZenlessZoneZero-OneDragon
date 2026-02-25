import os
import yaml
from datetime import datetime
from fastapi import HTTPException
from zzz_data_model import BattleInfo, get_db_session
import requests

# 初始化
session = get_db_session()


async def save_battle(battle_name: str, file, creation_name: str, creation_date: datetime):
    try:
        # 检查 battle_name 是否已存在
        existing_battle = session.query(BattleInfo).filter_by(battle_name=battle_name).first()
        if existing_battle:
            # 删除旧的文件
            if os.path.exists(existing_battle.battle_url):
                os.remove(existing_battle.battle_url)

        # 如果file是URL，则下载文件
        if isinstance(file, str) and (file.startswith('http://') or file.startswith('https://')):
            response = requests.get(file)
            if response.status_code != 200:
                return HTTPException(status_code=400, detail='无法从提供的URL下载文件')
            file_content = response.content
            file_extension = '.yml'
        else:
            # 对于上传的文件
            file_extension = os.path.splitext(file.filename)[1]
            if file_extension.lower() not in ('.yml', '.yaml'):
                return HTTPException(status_code=400, detail='文件格式不正确，只支持 YAML 文件')
            file_content = await file.read()  # 使用 await 读取文件内容

        # 确保目录存在
        if not os.path.exists("battle"):
            os.makedirs("battle")

        # 构建文件路径
        file_path = f"battle/{battle_name}{file_extension}"

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)

        # 尝试读取 YAML 文件
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as e:
            os.remove(file_path)
            return HTTPException(status_code=400, detail=f"文件内容不正确，无法解析为 YAML：{e}")

        # 更新或插入新记录到数据库
        if existing_battle:
            # 更新现有记录
            existing_battle.battle_url = file_path
            existing_battle.creation_name = creation_name
            existing_battle.creation_date = creation_date
            session.commit()
        else:
            # 插入新记录
            new_battle = BattleInfo(
                battle_name=battle_name,
                battle_url=file_path,
                creation_name=creation_name,
                creation_date=creation_date
            )
            session.add(new_battle)
            session.commit()
    except Exception:
        session.rollback()
        raise  # 可以选择抛出异常，以便调用者可以捕捉到错误
    finally:
        session.close()

    return HTTPException(status_code=200)
