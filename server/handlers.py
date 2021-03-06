import json
import time
import cv2
import os
import numpy as np
from server.model import cnn_mnist
from server.model import cnn_cifar
from flask import Response, request
from server.image_cli import ImageCli
from server import config
from werkzeug.utils import secure_filename

import server.deployer as deployer

from server.dal.entities import Model, Deploy
from server.dal import DBSession


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return round(float(obj), 4)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(MyEncoder, self).default(obj)


def _hello():
    resp = Response(mimetype='application/json')
    resp.set_data(u'{"hello": "world"}');
    return resp

def _train_model(name, conf, file_path):
    if name == "CNN":
        dic = json.loads(conf)
        cnn_mnist.set_parameter(dic)
        train_ret = cnn_mnist.train(file_path)
        m = Model()
        m.saved_path = train_ret['save_path']
        m.type = 1
        m.name = 'cnn'
        m.hyper_params = conf
        m.accuracy = train_ret['acc']

        with DBSession() as sess:
            sess.add(m)
            sess.commit()

        print('Insert a trained model. id=%d' % m.mid)

        train_ret['mid'] = m.mid

        ans = {}
        ans['Conf'] = dic
        ans['Result'] = train_ret

        return json.dumps(ans, cls=MyEncoder)

def _train(req=request):
    if req.method == "POST":
        f = req.files['file']
        conf = req.form['conf']
        name = req.form['model']
        file_path = os.path.join(config.upload_path, f.filename)
        f.save(file_path)

        #print(upload_path)
        return _train_model(name, conf, file_path)

    resp = Response(mimetype='text/plain')
    resp.set_data(u'Task submit successful!');
    return resp

def _deploy(req = request):
    if req.method == "POST":
        mid = req.form['mid']
        ret = deployer.deploy_model(mid)

    resp = Response(mimetype='application/json')
    resp.set_data(u'{"code": 0, "msg": "depoly successful"}');
    return resp

def _get_modellist(req = request):
    models = []
    with DBSession() as sess:
        for m in sess.query(Model).all():
            d = {}
            d['id'] = m.mid
            d['model'] = m.name
            d['acc'] = float(m.accuracy)
            d['conf'] = m.hyper_params
            models.append(d)

    resp = {}
    resp['code'] = 0
    resp['msg'] = ''
    resp['count'] = len(models)
    resp['data'] = models

    return json.dumps(resp, cls=MyEncoder)

serv_clis = []

def _img_ping():
    global serv_clis
    if len(serv_clis) == 0:
        imgcli = ImageCli()
        imgcli.connect()
        serv_clis.append(imgcli)
    else:
        imgcli = serv_clis[0]

    ret = imgcli.client.ping()
    resp = Response(mimetype='application/json')
    resp.set_data(u'{"state": "%s"}' % ret);
    return resp


def _img_predict(req=request):
    f = req.files['file']
    file_path = os.path.join(config.upload_path, f.filename)
    f.save(file_path)

    print('img_predict: file saved: %s' % file_path)
    global serv_clis
    if len(serv_clis) == 0:
        imgcli = ImageCli()
        imgcli.connect()
        serv_clis.append(imgcli)
    else:
        imgcli = serv_clis[0]

    ret = imgcli.client.predict(file_path)
    print('_img_predict: prediction=%s' % ret)

    return u'{"code": 0, "result": "%s"}' % ret[0]

def _get_model_list(req = request):
    return '{"code":0,"msg":"","count":1,"data":[{"id": 10000, "model": "CNN", "acc": 0.998, "conf": "{\\\"learning_rate\\\":0.001,\\\"num_steps\\\":2,\\\"batch_size\\\":128}"}]}';
    #return '{"code":0,"msg":"","count":1,"data":[{"id":10002,"model":"user-2","acc":"女","conf":"城市-2"}]}';

def get_endpoints():
    """
    :return: List of tuples (path, handler, methods)
    """
    # a fake handler
    ret = [('/api/hello', HANDLERS['hello'], ['GET']),
            ('/api/train', HANDLERS['train'], ['POST']),
            ('/api/deploy', HANDLERS['deploy'], ['POST', 'GET']),
            ('/api/img_predict', HANDLERS['img_predict'], ['POST', 'GET']),
            ('/api/get_model_list', HANDLERS['get_model_list'], ['POST', 'GET']),
            ]
    return ret


# dict of handlers
HANDLERS = {
        "hello": _hello,
        'train': _train,
        'deploy': _deploy,
        'img_predict': _img_predict,
        # 'get_modellist': _get_modellist,
        'get_model_list': _get_modellist,
}
