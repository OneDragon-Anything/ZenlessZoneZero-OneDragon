from enum import StrEnum


class RouteListType(StrEnum):
    """路线列表类型"""
    WHITELIST = 'whitelist'  # 白名单
    BLACKLIST = 'blacklist'  # 黑名单


class WorldPatrolRouteList:
    """世界巡逻路线列表"""
    
    def __init__(
            self,
            name: str,
            list_type: RouteListType,
            route_items: list[str] = None
    ):
        self.name: str = name
        self.list_type: RouteListType = list_type
        self.route_items: list[str] = [] if route_items is None else route_items
        
    def add_route(self, route_full_id: str):
        """添加单条路线"""
        self.route_items.append(route_full_id)
            
    def remove_route(self, route_full_id: str):
        """移除路线"""
        self.route_items.remove(route_full_id)
            
    def move_route(self, from_index: int, to_index: int):
        """移动路线顺序"""
        if 0 <= from_index < len(self.route_items) and 0 <= to_index < len(self.route_items):
            item = self.route_items.pop(from_index)
            self.route_items.insert(to_index, item)
            
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'list_type': str(self.list_type),
            'route_items': self.route_items
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'WorldPatrolRouteList':
        return cls(
            name=data['name'],
            list_type=RouteListType(data['list_type']),
            route_items=data.get('route_items', []),
        )
