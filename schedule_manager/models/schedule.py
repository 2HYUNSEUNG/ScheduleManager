# models/schedule.py
class DailySchedule:
    def __init__(self, date):
        self.date = date              # YYYY-MM-DD
        self.working = {'옥수': [], '효창': []}  # 각 지점 근무자 리스트 (직원 ID)
        self.holidays = []            # 휴무자 리스트 (직원 ID)
        self.memo = ''                 # 메모
        self.closed = False            # 가게 전체 휴업 여부

    def to_dict(self):
        return {
            'date': self.date,
            'working': self.working,
            'holidays': self.holidays,
            'memo': self.memo,
            'closed': self.closed
        }

    @staticmethod
    def from_dict(data):
        ds = DailySchedule(data['date'])
        ds.working = data['working']
        ds.holidays = data['holidays']
        ds.memo = data['memo']
        ds.closed = data['closed']
        return ds
