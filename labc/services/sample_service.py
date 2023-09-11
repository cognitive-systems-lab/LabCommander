from labc import register, register_service

@register_service(name="labc.SampleService")
class SampleService:
    def __init__(self):
        print("sample service created")
    
    @register
    def print_(self):
        print("print_ called")
