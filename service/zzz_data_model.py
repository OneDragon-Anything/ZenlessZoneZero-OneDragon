from sqlalchemy import Column, Integer, String, DateTime, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime

# 数据模型定义
Base = declarative_base()

# 数据库连接配置
DATABASE_URI = "mysql+pymysql://zzz_database:zzz_database@127.0.0.1:3306/zzz_database"

# 创建引擎
engine = create_engine(DATABASE_URI)

# 创建会话工厂
Session = sessionmaker(bind=engine)

# 使用 scoped_session 来确保线程安全
ScopedSession = scoped_session(Session)
session = ScopedSession()

# 确保表已创建
Base.metadata.create_all(engine)


def get_db_session():
    """ 获取当前线程的数据库会话 """
    return session


def get_battle_info():
    try:
        return session.query(BattleInfo).order_by(BattleInfo.creation_date.desc()).all()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_battle_url(bid):
    try:
        return session.query(BattleInfo).filter_by(id=bid).first()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_battle_by_name(battle_name):
    try:
        return session.query(BattleInfo).filter_by(battle_name=battle_name).first()
    except Exception:
        session.rollback()
    finally:
        session.close()


def clear_battle_info_table():
    try:
        session.execute(delete(BattleInfo))
        session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()


class BattleInfo(Base):
    __tablename__ = 'battle_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    battle_name = Column(String(30), unique=True, nullable=False)
    battle_url = Column(String(50))
    creation_name = Column(String(30))
    creation_date = Column(DateTime, default=datetime.now)
