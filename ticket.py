import base64
import json
import os
import re
import threading
import time
import urllib.request

import requests  # 用requests库，方便保存会话 功能和urllib差不多
from bs4 import BeautifulSoup, SoupStrainer  # 网页解析库 可以替代正则来获取你想要的内容
from PIL import Image  # 操作图片
from requests.packages import urllib3

urllib3.disable_warnings()
session = requests.Session()  # session会话对象，请求和返回的信息保存在session中
session.verify = False


def get(url):
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:64.0) Gecko/20100101 Firefox/64.0"
    }
    reqs = session.get(url, headers=header)
    reqs.encoding = 'UTF-8-SIG'
    if(reqs.text.find('网络可能存在问题') > -1 or reqs.text.find('您选择的日期不在预售期范围内') > -1):
        print('网络可能存在问题')
        return ''
    return reqs.text


def post(url, data):
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:64.0) Gecko/20100101 Firefox/64.0"
    }
    reqs = session.post(url, headers=header, data=data)
    reqs.encoding = 'UTF-8-SIG'
    if(reqs.text.find('网络可能存在问题') > -1 or reqs.text.find('您选择的日期不在预售期范围内') > -1):
        print('网络可能存在问题')
        return ''
    return reqs.text


def Convert(val):
    if(val == '无' or val == ''):
        return 0
    elif(val == '有'):
        return 20
    return int(val)


with open('./city.json', encoding='utf-8') as f:
    CITY_DATA = json.load(f)

# 保存cookie


def saveCookie():
    _cookies = session.cookies.get_dict()
    # 取到session的cookie信息 取出来是键值对把他转化成字符串类型保存下来
    cookieStr = json.dumps(_cookies)
    with open('./cookies.txt', 'w') as f:
        f.write(cookieStr)
        print('记录cookie成功')

# 取出cookie


def getCookie():
    try:
        with open('./cookies.txt', 'r') as f:
            _cookie = json.load(f)
            # session的cookie是一个RequestsCookieJar类型的，把键值对转换为给他
            session.cookies = requests.utils.cookiejar_from_dict(_cookie)
    except FileNotFoundError:
        print('还未登陆过..')

# 获取二维码图片


def getQR():
    data = post(
        'https://kyfw.12306.cn/passport/web/create-qr64', {"appid": "otn"})
    json_result = json.loads(data)  # 是json格式 直接转成json方便操作
    if(json_result['result_code'] == "0"):
        uuid = json_result['uuid']
        threading._start_new_thread(checkqr, (uuid,))  # 开一个线程去执行监听

        login_pic = getImage(base64.b64decode(json_result['image']))
        Image.open(login_pic).show()  # 依赖PIL库，打开图片(会创建一个零食文件打开图片，图片未被占用时销毁)


def getImage(img):
    filepath = './login.png'
    with open(filepath, 'wb') as fd:  # w写入 b二进制形式
        fd.write(img)
    return filepath


def checkqr(uuid):
    while(True):
        checkqr_url = 'https://kyfw.12306.cn/passport/web/checkqr'
        data = post(checkqr_url, {"uuid": uuid, "appid": "otn"})
        json_result = json.loads(data)
        status_code = json_result['result_code']
        if(status_code == "1"):
            print('已扫描请确定')
        elif(status_code == "2"):
            print(json_result['result_message'])
            auth()
            return
        elif(status_code == '3'):  # 二维码过期
            getQR()
            return
        time.sleep(2)


# 检查是否登陆
def checkuser():
    getCookie()

    url = 'https://kyfw.12306.cn/otn/login/checkUser'
    data = post(url, {"_json_att: ": ""})
    json_result = json.loads(data)
    print(json_result)
    if (json_result['status']):
        if(json_result['data']['flag']):
            return json_result['data']['flag']
        else:
            getQR()
    return False

# 扫码之后验证


def auth():
    try:
        data = post('https://kyfw.12306.cn/passport/web/auth/uamtk',
                    {"appid": "otn"})
        json_result = json.loads(data)
        if(json_result['result_code'] == 1):
            checkuser()
            return

        authinfo = post('https://kyfw.12306.cn/otn/uamauthclient',
                        {"tk": json_result['newapptk']})
        json_result = json.loads(authinfo)
        if(json_result['result_code'] == 0):  # 登陆成功后保存cookie
            saveCookie()
            print("登陆成功，用户名："+json_result["username"])
    except json.decoder.JSONDecodeError:  # 转json失败 一般就是验证失败了 回来的一般是让你登陆的
        print('验证失败')


select_ticket_URL = 'leftTicket/queryA'  # 查票的地址是在queryA、queryZ啥的随机变化的
# 查票


def select_ticket():
    initTicketDTO()
    global select_ticket_URL  # 查询的query后会随机变成AZ什么的
    url = 'https://kyfw.12306.cn/otn/'+select_ticket_URL +\
        '?leftTicketDTO.train_date='+TicketDTO['train_date'] + \
        '&leftTicketDTO.from_station=' + TicketDTO['from_station'] +\
        '&leftTicketDTO.to_station='+TicketDTO['to_station'] +\
        '&purpose_codes=ADULT'  # ADULT：普通票
    data = get(url)

    json_result = json.loads(data)
    if(not json_result['status']):
        select_ticket_URL = json_result['c_url']
        select_ticket()
        return
    city_info = json_result['data']['map']  # 城市信息
    for item in json_result['data']['result']:
        classes = item.split('|')  # 被竖线隔开的
        canBuy = classes[11]  # 是否可购买
        secretStr = urllib.request.unquote(classes[0])  # 下单信息
        IsEnable = (classes[0] == "" and False or True)  # 有无预定信息
        train_no = classes[2]  # 班次
        TrainClass = classes[3]  # 班次
        FirstSeat = classes[31]  # 一等座
        SecondSeat = Convert(classes[30])   # 二等座
        #print(canBuy+"=> 班次："+TrainClass+" 历程：" + classes[13]+" "+city_info[classes[6]]+"=>"+city_info[classes[7]] + " "+classes[8]+"-" + classes[9]+"["+classes[10] + "h] 一等座："+str(FirstSeat)+" 二等座："+str(SecondSeat))
        if(TrainClass in TicketDTO['class']):
            print(train_no+"：二等座余票："+str(SecondSeat))
            if(IsEnable and canBuy == 'Y'):  # 有提交信息 并且可以购买
                print('检测到余票，正在提交')
                NowTrainInfo = {"train_no": train_no, "TrainClass": TrainClass,
                                "from_station": classes[6], "to_station": classes[7]}
                print(NowTrainInfo)
                if(SecondSeat > 0):
                    while True:
                        json_initDc = submitOrderRequest(secretStr)
                        checkOrderInfo(json_initDc, NowTrainInfo)
                        time.sleep(2)


# 检测是否有未完成的订单，没有的话获取购票人
def submitOrderRequest(secretStr):
    reqdata = {
        "secretStr": secretStr,
        "train_date": TicketDTO['train_date'],
        "back_train_date": time.strftime('%Y-%m-%d', time.localtime(time.time())),
        "tour_flag": 'dc',
        "purpose_codes": 'ADULT',
        "query_from_station_name": TicketDTO['from_station_name'],
        "query_to_station_name": TicketDTO['to_station_name'],
        "undefined": ''
    }
    url = 'https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest'
    data = post(url, reqdata)
    json_result = json.loads(data)
    if(json_result['data'] == 'N' and json_result['status']):  # 无未完成的订单\
        json_initDc = getinitDc()
        if(getPassenge(json_initDc['REPEAT_SUBMIT_TOKEN'])):
            return json_initDc


def getinitDc():
    html_data = post('https://kyfw.12306.cn/otn/confirmPassenger/initDc',
                     {"_json_att: ": ""})
    REPEAT_SUBMIT_TOKEN = re.findall(re.compile(
        "var globalRepeatSubmitToken = '(.*?)';", re.S), html_data)
    key_check_isChange = re.findall(re.compile(
        "'key_check_isChange':'(.*?)',", re.S), html_data)
    leftTicketStr = re.findall(re.compile(
        "'leftTicketStr':'(.*?)',", re.S), html_data)
    tour_flag = re.findall(re.compile(
        ",'tour_flag':'(.*?)',", re.S), html_data)
    purpose_codes = re.findall(re.compile(
        ",'purpose_codes':'(.*?)',", re.S), html_data)
    train_location = re.findall(re.compile(
        ",'train_location':'(.*?)'", re.S), html_data)
    train_no = re.findall(re.compile(",'train_no':'(.*?)',", re.S), html_data)
    station_train_code = re.findall(re.compile(
        ",'station_train_code':'(.*?)',", re.S), html_data)
    from_station_telecode = re.findall(re.compile(
        ",'from_station_telecode':'(.*?)',", re.S), html_data)
    to_station = re.findall(re.compile(
        ",'to_station':'(.*?)',", re.S), html_data)

    json_initDc = {
        'REPEAT_SUBMIT_TOKEN': REPEAT_SUBMIT_TOKEN,
        'key_check_isChange': key_check_isChange,
        'leftTicketStr': leftTicketStr,
        'tour_flag': tour_flag,
        'purpose_codes': purpose_codes,
        'train_location': train_location,
        'train_no': train_no,
        'station_train_code': station_train_code,
        'from_station_telecode': from_station_telecode,
        'to_station': to_station
    }
    return json_initDc


def getPassenge(REPEAT_SUBMIT_TOKEN):
    if(any(TicketDTO['passengerInfo'])):
        return True
    else:
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs'
        reqdata = {
            "_json_att: ": "",
            "REPEAT_SUBMIT_TOKEN": REPEAT_SUBMIT_TOKEN[0]
        }
        data = post(url, reqdata)
        json_result = json.loads(data)
        print("购票人数据：")
        for item in json_result['data']['normal_passengers']:
            if item['passenger_name'] in TicketDTO['holder']:
                TicketDTO['passengerInfo'] = {'passengerTicketStr': 'O,'+item['passenger_flag']+','+item['passenger_type']+','+item['passenger_name']+','+item['passenger_id_type_code']+','+item['passenger_id_no']+','+item['mobile_no']+',N',
                                              'oldPassengerStr': item['passenger_name']+','+item['passenger_id_type_code']+','+item['passenger_id_no'] + ',1_'}
        if(any(TicketDTO['passengerInfo'])):
            return True


# 买票
def checkOrderInfo(json_initDc, NowTrainInfo):
    # 检查确定订单信息
    reqdata = {
        'cancel_flag': '2', #固定
        'bed_level_order_num': '000000000000000000000000000000',
        'passengerTicketStr': TicketDTO['passengerInfo']['passengerTicketStr'],
        'oldPassengerStr': TicketDTO['passengerInfo']['oldPassengerStr'],
        'tour_flag': json_initDc['tour_flag'],  # 基本固定
        'randCode': '',
        'whatsSelect': '1',  # 固定
        '_json_att': '',  # 为空
        'REPEAT_SUBMIT_TOKEN': json_initDc['REPEAT_SUBMIT_TOKEN']
    }

    data = post(
        'https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo', reqdata)
    json_result = json.loads(data)
    # {"validateMessagesShowId":"_validatorMessage","status":true,"httpstatus":200,"data":{"ifShowPassCode":"N","canChooseBeds":"N","canChooseSeats":"Y","choose_Seats":"O","isCanChooseMid":"N","ifShowPassCodeTime":"1","submitStatus":true,"smokeStr":""},"messages":[],"validateMessages":{}}
    if(not json_result['status']):
        print('no')
        return

    stra = time.strftime("%a+%b+%d+%Y+00:00:00+GMT+0800", time.strptime(
        TicketDTO['train_date'], "%Y-%m-%d %H:%M:%S"))+'+(中国标准时间)'
    # 获取余票
    reqdata = {
        'train_date': time.strftime("%a+%b+%d+%Y+00:00:00+GMT+0800", time.strptime(TicketDTO['train_date'], "%Y-%m-%d %H:%M:%S"))+'+(中国标准时间)',
        'train_no': json_initDc['train_no'],  # 班次号
        'stationTrainCode': json_initDc['station_train_code'],  # 车次
        'seatType': json_result['choose_Seats'],  # ？？ 上面返回的 就是你选座的类型
        'fromStationTelecode': json_initDc['from_station'],  # 起点终点
        'toStationTelecode': json_initDc['to_station'],
        'leftTicket': json_initDc['leftTicketStr'],
        'purpose_codes': json_initDc['purpose_codes'],  # ?? 姑且认为是固定  没有取不到的参数！
        'train_location': json_initDc['train_location'],  # ??
        '_json_att': '',
        'REPEAT_SUBMIT_TOKEN': json_initDc['REPEAT_SUBMIT_TOKEN']
    }
    data = post(
        'https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount', reqdata)

    # 请求车票
    reqdata = {
        'passengerTicketStr': TicketDTO['passengerInfo']['passengerTicketStr'],
        'oldPassengerStr': TicketDTO['passengerInfo']['oldPassengerStr'],
        'randCode': '',
        'purpose_codes': json_initDc['purpose_codes'], 
        'key_check_isChange': json_initDc['key_check_isChange'],
        'leftTicketStr': json_initDc['leftTicketStr'],
         'train_location': json_initDc['train_location'], 
        'choose_seats': '1D',  # ??  选择的座位
        'seatDetailType': '000', # 固定
        'whatsSelect': '1',# 固定
        'roomType': '00',# 固定
        'dwAll': 'N',# 固定
        '_json_att': '',# 固定
        'REPEAT_SUBMIT_TOKEN': json_initDc['REPEAT_SUBMIT_TOKEN']
    }
    data = post(
        'https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount', reqdata)


TicketDTO = {}  # 封装请求参数


def initTicketDTO():
    TicketDTO['train_date'] = '2019-02-10'
    TicketDTO['from_station_name'] = '重庆'
    TicketDTO['to_station_name'] = ''
    TicketDTO['class'] = ['D5147']
    TicketDTO['holder'] = ['']

    TicketDTO['from_station'] = CITY_DATA[TicketDTO['from_station_name']]
    TicketDTO['to_station'] = CITY_DATA[TicketDTO['to_station_name']]

    TicketDTO['passengerInfo'] = {}


if __name__ == "__main__":
    checkuser()
    select_ticket()
'''
    getPassenge()


    initTicketDTO()
    print(TicketDTO)
    select_ticket()
'''
