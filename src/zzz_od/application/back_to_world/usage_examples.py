"""
返回大世界应用使用示例

展示如何在代码中使用返回大世界应用
"""

# 示例1: 在应用链中调用返回大世界
def example_in_application_chain():
    """
    在一个应用执行完成后，自动返回大世界
    """
    from zzz_od.context.zzz_context import ZContext
    from zzz_od.application.email_app.email_app import EmailApp
    from zzz_od.application.back_to_world.back_to_world_app import BackToWorldApp
    
    ctx = ZContext()
    ctx.init()
    
    # 先执行邮件应用
    email_app = EmailApp(ctx)
    email_app.execute()
    
    # 然后返回大世界
    back_to_world_app = BackToWorldApp(ctx)
    back_to_world_app.execute()


# 示例2: 作为独立应用运行
def example_standalone():
    """
    单独运行返回大世界应用
    """
    from zzz_od.context.zzz_context import ZContext
    from zzz_od.application.back_to_world.back_to_world_app import BackToWorldApp
    
    ctx = ZContext()
    ctx.init()
    
    app = BackToWorldApp(ctx)
    result = app.execute()
    
    if result.is_success:
        print("成功返回大世界")
    else:
        print(f"返回大世界失败: {result.status}")


# 示例3: 在自定义操作中嵌入返回大世界逻辑
def example_embedded_in_operation():
    """
    在自定义操作中直接使用返回大世界的逻辑
    """
    from zzz_od.context.zzz_context import ZContext
    from zzz_od.operation.back_to_normal_world import BackToNormalWorld
    
    ctx = ZContext()
    ctx.init()
    
    # 直接调用操作，而不是通过应用
    op = BackToNormalWorld(ctx)
    result = op.execute()
    
    if result.is_success:
        print(f"成功返回大世界，当前状态: {result.status}")
    else:
        print(f"返回失败: {result.error_str}")


if __name__ == '__main__':
    print("返回大世界应用使用示例")
    print("=" * 50)
    print("\n示例1: 在应用链中调用")
    print("  - 先执行邮件应用")
    print("  - 然后自动返回大世界")
    print("\n示例2: 作为独立应用运行")
    print("  - 直接运行返回大世界应用")
    print("\n示例3: 在自定义操作中嵌入")
    print("  - 直接使用 BackToNormalWorld 操作")
    print("\n注意: 这些示例需要在游戏运行时执行")
