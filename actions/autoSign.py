import json
import re

from requests_toolbelt import MultipartEncoder

from todayLoginService import TodayLoginService
from liteTools import LL, DT, RT, MT, TaskError, CpdailyTools


class AutoSign:
    # 初始化签到类
    def __init__(self, todayLoginService: TodayLoginService, userInfo):
        self.session = todayLoginService.session
        self.host = todayLoginService.host
        self.userInfo = userInfo
        self.taskInfo = None
        self.task = None
        self.form = {}
        self.fileName = None

    # 获取未签到的任务

    def getUnSignTask(self):
        LL.log(1, '获取未签到的任务')
        headers = self.session.headers
        headers['Content-Type'] = 'application/json'
        # 第一次请求接口获取cookies（MOD_AUTH_CAS）
        url = f'{self.host}wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay'
        self.session.post(url, headers=headers,
                          data=json.dumps({}), verify=False)
        # 第二次请求接口，真正的拿到具体任务
        res = self.session.post(url, headers=headers,
                                data=json.dumps({}), verify=False)
        res = DT.resJsonEncode(res)
        LL.log(1, '返回的列表数据', res['datas'])

        signLevel = self.userInfo.get('signLevel', 1)
        if signLevel >= 0:
            taskList = res['datas']['unSignedTasks']  # 未签到任务
        if signLevel >= 1:
            taskList += res['datas']['leaveTasks']  # 不需签到任务
        if signLevel == 2:
            taskList += res['datas']['signedTasks']  # 已签到任务
        # 查询是否没有未签到任务
        if len(taskList) < 1:
            LL.log(1, '无需要签到的任务')
            raise TaskError('无需要签到的任务')
        if self.userInfo.get('title'):
            # 获取匹配标题的任务
            for righttask in taskList:
                if re.search(self.userInfo['title'], righttask['taskName']):
                    self.taskName = righttask['taskName']
                    LL.log(1, '匹配标题的任务', righttask['taskName'])
                    self.taskInfo = {'signInstanceWid': righttask['signInstanceWid'],
                                     'signWid': righttask['signWid'], 'taskName': righttask['taskName']}
                    return self.taskInfo
            # 如果没有找到匹配的任务
            LL.log(1, '没有匹配标题的任务')
            raise TaskError('没有匹配标题的任务')
        else:  # 如果没有填title字段
            # 自动获取最后一个未签到任务
            latestTask = taskList[0]
            self.taskName = latestTask['taskName']
            LL.log(1, '最后一个未签到的任务', latestTask['taskName'])
            self.taskInfo = {'signInstanceWid': latestTask['signInstanceWid'],
                             'signWid': latestTask['signWid'], 'taskName': latestTask['taskName']}
            return self.taskInfo

    # 获取历史签到任务详情
    def getHistoryTaskInfo(self):
        '''获取历史签到任务详情'''
        headers = self.session.headers
        headers['Content-Type'] = 'application/json;charset=UTF-8'

        # 获取签到月历
        url = f'{self.host}wec-counselor-sign-apps/stu/sign/getStuIntervalMonths'
        res = self.session.post(url, headers=headers,
                                data=json.dumps({}), verify=False)
        res = DT.resJsonEncode(res)
        monthList = [i['id'] for i in res['datas']['rows']]
        monthList.sort(reverse=True)  # 降序排序月份

        # 按月遍历
        for month in monthList:
            # 获取对应历史月签到情况
            req = {"statisticYearMonth": month}
            url = f'{self.host}wec-counselor-sign-apps/stu/sign/getStuSignInfosByWeekMonth'
            res = self.session.post(
                url, headers=headers, data=json.dumps(req), verify=False)
            res = DT.resJsonEncode(res)
            monthSignList = list(res['datas']['rows'])
            # 遍历查找历史月中每日的签到情况
            monthSignList.sort(
                key=lambda x: x['dayInMonth'], reverse=True)  # 降序排序日信息
            for daySignList in monthSignList:
                # 遍历寻找和当前任务匹配的历史已签到任务
                for task in daySignList['signedTasks']:
                    if task['signWid'] == self.taskInfo['signWid']:
                        # 找到和当前任务匹配的历史已签到任务，开始获取表单
                        historyTaskId = {
                            "wid": task['signInstanceWid'], "content": task['signWid']}
                        # 更新cookie
                        url = f'{self.host}wec-counselor-sign-apps/stu/sign/getUnSeenQuestion'
                        self.session.post(url, headers=headers, data=json.dumps(
                            historyTaskId), verify=False)
                        # 获取历史任务详情
                        historyTaskId = {
                            "signInstanceWid": task['signInstanceWid'], "signWid": task['signWid']}
                        url = f'{self.host}wec-counselor-sign-apps/stu/sign/detailSignInstance'
                        res = self.session.post(
                            url, headers=headers, data=json.dumps(historyTaskId), verify=False)
                        res = DT.resJsonEncode(res)
                        # 其他模拟请求
                        url = f'{self.host}wec-counselor-sign-apps/stu/sign/queryNotice'
                        self.session.post(url, headers=headers,
                                          data=json.dumps({}), verify=False)
                        url = f'{self.host}wec-counselor-sign-apps/stu/sign/getQAconfigration'
                        self.session.post(url, headers=headers,
                                          data=json.dumps({}), verify=False)
                        # 一些数据处理
                        result = res['datas']

                        # 坐标随机
                        result['longitude'] = float(result['longitude'])
                        result['latitude'] = float(result['latitude'])
                        result['longitude'], result['latitude'] = RT.locationOffset(
                            result['longitude'], result['latitude'], self.userInfo['global_locationOffsetRange'])

                        result['photograph'] = result['photograph'] if len(
                            result['photograph']) != 0 else ""
                        result['extraFieldItems'] = [{"extraFieldItemValue": i['extraFieldItem'],
                                                      "extraFieldItemWid": i['extraFieldItemWid']} for i in result['signedStuInfo']['extraFieldItemVos']]
                        # 返回结果
                        LL.log(1, '历史签到情况的详情', result)
                        self.historyTaskInfo = result
                        return result

        # 如果没有遍历找到结果
        LL.log(2, "没有找到匹配的历史任务")
        raise TaskError("没有找到匹配的历史任务")

    def getDetailTask(self):
        LL.log(1, '获取具体的签到任务详情')
        url = f'{self.host}wec-counselor-sign-apps/stu/sign/detailSignInstance'
        headers = self.session.headers
        headers['Content-Type'] = 'application/json;charset=UTF-8'
        res = self.session.post(url, headers=headers, data=json.dumps(
            self.taskInfo), verify=False)
        res = DT.resJsonEncode(res)
        LL.log(1, '签到任务的详情', res['datas'])
        self.task = res['datas']



    # 填充表单
    def fillForm(self):
        LL.log(1, '填充表单')
        if self.userInfo['getHistorySign']:
            self.getHistoryTaskInfo()
            hti = self.historyTaskInfo

            self.form['isNeedExtra'] = self.task['isNeedExtra']
            self.form['signInstanceWid'] = self.task['signInstanceWid']

            self.form['signPhotoUrl'] = hti['signPhotoUrl']
            self.form['extraFieldItems'] = hti['extraFieldItems']
            self.form['longitude'], self.form['latitude'] = hti['longitude'], hti['latitude']
            # 检查是否在签到范围内
            self.form['isMalposition'] = 1
            for place in self.task['signPlaceSelected']:
                if MT.geoDistance(self.form['longitude'], self.form['latitude'], place['longitude'], place['latitude']) < place['radius']:
                    self.form['isMalposition'] = 0
                    break
            self.form['abnormalReason'] = hti.get(
                'abnormalReason', '回家')  # WARNING: 未在历史信息中找到这个
            self.form['position'] = hti['signAddress']
            self.form['uaIsCpadaily'] = True
            self.form['signVersion'] = '1.0.0'
        else:
            # 判断签到是否需要照片
            if self.task['isPhoto'] == 1:
                pic = self.userInfo['photo']
                picBlob, picType = RT.choicePhoto(pic, dirTimeFormat=True)
                # 上传图片
                url_getUploadPolicy = f'{self.host}wec-counselor-sign-apps/stu/obs/getUploadPolicy'
                ossKey = CpdailyTools.uploadPicture(
                    url_getUploadPolicy, self.session, picBlob, picType)
                # 获取图片url
                url_previewAttachment = f'{self.host}wec-counselor-sign-apps/stu/sign/previewAttachment'
                imgUrl = CpdailyTools.getPictureUrl(
                    url_previewAttachment, self.session, ossKey)
                self.form['signPhotoUrl'] = imgUrl
            else:
                self.form['signPhotoUrl'] = ''
            # 检查是否需要额外信息
            self.form['isNeedExtra'] = self.task['isNeedExtra']
            if self.task['isNeedExtra'] == 1:
                extraFields = self.task['extraField']
                userItems = self.userInfo['forms']
                extraFieldItemValues = []
                for i in range(len(extraFields)):
                    userItem = userItems[i]['form']
                    extraField = extraFields[i]
                    if self.userInfo['checkTitle'] == 1:
                        if userItem['title'] != extraField['title']:
                            raise Exception(
                                f'\r\n第{i + 1}个配置出错了\r\n您的标题为：{userItem["title"]}\r\n系统的标题为：{extraField["title"]}')
                    extraFieldItems = extraField['extraFieldItems']
                    flag = False
                    for extraFieldItem in extraFieldItems:
                        if extraFieldItem['isSelected']:
                            data = extraFieldItem['content']
                        if extraFieldItem['content'] == userItem['value']:
                            flag = True
                            extraFieldItemValue = {'extraFieldItemValue': userItem['value'],
                                                   'extraFieldItemWid': extraFieldItem['wid']}
                            # 其他 额外的文本
                            if extraFieldItem['isOtherItems'] == 1:
                                flag = True
                                extraFieldItemValue = {'extraFieldItemValue': userItem['extraValue'],
                                                       'extraFieldItemWid': extraFieldItem['wid']}
                            extraFieldItemValues.append(extraFieldItemValue)
                    if not flag:
                        raise Exception(
                            f'\r\n第{ i + 1 }个配置出错了\r\n表单未找到你设置的值：{userItem["value"]}\r\n，你上次系统选的值为：{ data }')
                self.form['extraFieldItems'] = extraFieldItemValues
            self.form['signInstanceWid'] = self.task['signInstanceWid']
            self.form['longitude'] = self.userInfo['lon']
            self.form['latitude'] = self.userInfo['lat']
            # 检查是否在签到范围内
            self.form['isMalposition'] = 1
            for place in self.task['signPlaceSelected']:
                if MT.geoDistance(self.form['longitude'], self.form['latitude'], place['longitude'], place['latitude']) < place['radius']:
                    self.form['isMalposition'] = 0
                    break
            self.form['abnormalReason'] = self.userInfo['abnormalReason']
            self.form['position'] = self.userInfo['address']
            self.form['uaIsCpadaily'] = True
            self.form['signVersion'] = '1.0.0'
        LL.log(1, "填充完毕的表单", self.form)

    def getSubmitExtension(self):
        '''生成各种额外参数'''
        extension = {
            "lon": self.form['longitude'],
            "lat": self.form['latitude'],
            "model": self.userInfo['model'],
            "appVersion": self.userInfo['appVersion'],
            "systemVersion": self.userInfo['systemVersion'],
            "userId": self.userInfo['username'],
            "systemName": self.userInfo['systemName'],
            "deviceId": self.userInfo['deviceId']
        }

        self.cpdailyExtension = CpdailyTools.encrypt_CpdailyExtension(
            json.dumps(extension))

        self.bodyString = CpdailyTools.encrypt_BodyString(
            json.dumps(self.form))

        self.submitData = {
            "lon": self.form['longitude'],
            "version": self.userInfo['signVersion'],
            "calVersion": self.userInfo['calVersion'],
            "deviceId": self.userInfo['deviceId'],
            "userId": self.userInfo['username'],
            "systemName": self.userInfo['systemName'],
            "bodyString": self.bodyString,
            "lat": self.form['latitude'],
            "systemVersion": self.userInfo['systemVersion'],
            "appVersion": self.userInfo['appVersion'],
            "model": self.userInfo['model'],
        }

        self.submitData['sign'] = CpdailyTools.signAbstract(self.submitData)

    # 提交签到信息
    def submitForm(self):
        LL.log(1, '提交签到信息')
        self.getSubmitExtension()

        headers = {
            'User-Agent': self.session.headers['User-Agent'],
            'CpdailyStandAlone': '0',
            'extension': '1',
            'Cpdaily-Extension': self.cpdailyExtension,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept-Encoding': 'gzip',
            'Host': re.findall('//(.*?)/', self.host)[0],
            'Connection': 'Keep-Alive'
        }

        LL.log(1, '即将提交的信息', headers, self.submitData)
        res = self.session.post(f'{self.host}wec-counselor-sign-apps/stu/sign/submitSign', headers=headers,
                                data=json.dumps(self.submitData), verify=False)
        res = DT.resJsonEncode(res)
        LL.log(1, '提交后返回的信息', res['message'])
        return '[%s]%s' % (res['message'], self.taskInfo['taskName'])
