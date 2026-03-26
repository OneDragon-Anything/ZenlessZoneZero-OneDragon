import requests

def rate_drive_disk(disk_data, character_name=None):
    url = 'http://localhost:3000/node-function'
    payload = {'diskData': disk_data}
    if character_name:
        payload['characterName'] = character_name
    response = requests.post(url, json=payload)
    return response.json()

# 测试单个驱动盘评分
single_disk_data = {
    "position": 1,
    "name": "测试驱动盘",
    "level": 10,
    "rarity": "S",
    "invalidProperty": 0,
    "mainProperty": {
        "name": "攻击力",
        "value": "+100"
    },
    "subProperties": [
        {
            "name": "暴击率",
            "value": "+10%",
            "level": 1,
            "valid": True,
            "add": 10
        },
        {
            "name": "暴击伤害",
            "value": "+20%",
            "level": 1,
            "valid": True,
            "add": 20
        }
    ]
}

print("测试单个驱动盘评分:")
result = rate_drive_disk(single_disk_data, "通用")
print(result)

# 测试角色全套驱动盘评分
multiple_disks_data = [
    {
        "position": 1,
        "name": "驱动盘1",
        "level": 10,
        "rarity": "S",
        "invalidProperty": 0,
        "mainProperty": {
            "name": "攻击力",
            "value": "+100"
        },
        "subProperties": [
            {
                "name": "暴击率",
                "value": "+10%",
                "level": 1,
                "valid": True,
                "add": 10
            }
        ]
    },
    {
        "position": 2,
        "name": "驱动盘2",
        "level": 10,
        "rarity": "A",
        "invalidProperty": 0,
        "mainProperty": {
            "name": "防御力",
            "value": "+50"
        },
        "subProperties": [
            {
                "name": "生命值",
                "value": "+1000",
                "level": 1,
                "valid": True,
                "add": 1000
            }
        ]
    }
]

print("\n测试角色全套驱动盘评分:")
result = rate_drive_disk(multiple_disks_data, "通用")
print(result)

# 测试获取支持的角色列表
print("\n测试获取支持的角色列表:")
response = requests.get('http://localhost:3000/characters')
print(response.json())