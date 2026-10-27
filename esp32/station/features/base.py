# Feature 契约：每个功能模块只实现这些钩子，网页/MQTT/日志自动接入。
class Feature:
    id = ""
    title = ""
    order = 100
    fields = []          # [{"key","label","unit"?}]
    card_fields = []     # 卡片上优先显示的字段 key
    actions = []         # [{"action","label","type":"button"/"range","min","max","value_key"}]
    list_key = None      # status 中的列表字段（详情页展示）
    list_label = None
    has_loop = False

    def __init__(self, app):
        self.app = app

    def init(self):
        pass

    def status(self):
        return {}

    def command(self, action, value=None):
        return {"ok": False, "error": "unsupported action"}

    async def loop(self):
        pass

    def meta(self):
        return {
            "id": self.id,
            "title": self.title,
            "order": self.order,
            "fields": self.fields,
            "card_fields": self.card_fields,
            "actions": self.actions,
            "list_key": self.list_key,
            "list_label": self.list_label,
        }
