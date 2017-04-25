#!/usr/bin/env python
# encoding: utf-8

import json
import time
import sys
import autoscale_config

from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.executor.playbook_executor import PlaybookExecutor

from ansible.plugins import callback_loader
from ansible.plugins.callback import CallbackBase

#import os
#import logging

Options = namedtuple('Options', ['connection', 'module_path', 'forks', 'become', 'become_method', 'become_user', 'check'])
options = Options(connection='smart', module_path=None, forks=10, become=None, become_method=None, become_user=None, check=False)
loader = DataLoader()
variable_manager = VariableManager()
inventory = Inventory(loader=loader, variable_manager=variable_manager)
variable_manager.set_inventory(inventory)

#get result output
class ResultsCollector(CallbackBase):
    def __init__(self, *args, **kwargs):
        super(ResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = []
        self.host_unreachable = []
        self.host_failed = []

    def v2_runner_on_unreachable(self, result, ignore_errors=False):
        name = result._host.get_name()
        task = result._task.get_name()
        print "ansible unreachable, name:%s, task:%s " % (nova, task)
        #ansible_log(result)
        #self.host_unreachable[result._host.get_name()] = result
        self.host_unreachable.append(dict(ip=name, task=task, result=result))

    def v2_runner_on_ok(self, result,  *args, **kwargs):
        #host = result._host
        #print json.dumps({host.name: result._result}, indent=4)
        name = result._host.get_name()
        task = result._task.get_name()
        if task == "setup":
            pass
        elif "Info" in task:
            self.host_ok.append(dict(ip=name, task=task, result=result))
        else:
            #ansible_log(result)
            self.host_ok.append(dict(ip=name, task=task, result=result))

    def v2_runner_on_failed(self, result,   *args, **kwargs):
        name = result._host.get_name()
        task = result._task.get_name()
        print "ansible failed, name:%s, task:%s" % (name, task)
        #ansible_log(result)
        self.host_failed.append(dict(ip=name, task=task, result=result))


def run_adhoc(ip,order):
    #variable_manager.extra_vars={"ansible_ssh_user":"root" , "ansible_ssh_pass":"passwd"}
    variable_manager.extra_vars={"ansible_ssh_user":"root"}
    play_source = {"name":"Openstack AutoScaling",
                   "hosts":"%s"%ip,
                   "gather_facts":"no",
                   #"tasks":[{"action":{"module":"command","args":"%s"%order}}]}
                   "tasks":[{"action":{"module":"shell","args":"%s"%order}}]}
#    play_source = {"name":"Ansible Ad-Hoc","hosts":"192.168.2.160","gather_facts":"no","tasks":[{"action":{"module":"command","args":"python ~/store.py del"}}]}
    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)
    tqm = None
    callback = ResultsCollector()

    try:
        tqm = TaskQueueManager(
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            options=options,
            passwords=None,
            #run_tree=False,
            #passwords = dict(vault_pass='hengcheng2016'),
            stdout_callback=callback,
        )
        #tqm._stdout_callback = callback
        result = tqm.run(play)
        return callback

    finally:
        if tqm is not None:
            tqm.cleanup()

def run_playbook(books):
    #results_callback = callback_loader.get('json')
    playbooks = [books]

    variable_manager.extra_vars={"ansible_ssh_user":"root" , "ansible_ssh_pass":"passwd"}
    callback = ResultsCollector()

    pd = PlaybookExecutor(
        playbooks=playbooks,
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        options=options,
        passwords=None,

        )
    pd._tqm._stdout_callback = callback

    try:
        result = pd.run()
        print result
        return callback

    except Exception as e:
        print e

def parse_la_vn(result):
    '''parse load average, vcpu number'''
    ret = result.split('\n')
    if len(ret) != 2:
        raise
    mark = 'load average:'
    ml = len(mark)
    la = ret[0][ret[0].find(mark) + ml:]
    la  = map(float, la.split(','))
    vn = int(ret[1])
    return {'la': la, 'vn': vn}

def ansible_command(controller, command):
    ret = run_adhoc(controller, command)
    if not ret.host_ok:
        raise
    return ret.host_ok[0]['result']._result['stdout']

def ansible_nova_resize(controller, ip):
    nova_virenv = autoscale_config.getConfig(conf_tag, "nova_virenv")
    nova_bin = autoscale_config.getConfig(conf_tag, "nova_bin")
    nova_argc = 'list --ip %s -c ID -f value' % ip
    command = nova_virenv + ' ' + nova_bin + ' ' + nova_argc
    print command
    instance_uuid = ansible_command(controller, command)
    #instance_uuid = 'aaaaaaaaaaaaaaaaaa'
    flavor = autoscale_config.getConfig(conf_tag, "resize_flavor")
    nova_argc = 'resize --flavor %s %s' % (flavor, instance_uuid)
    command = nova_virenv + ' ' + nova_bin + ' ' + nova_argc
    print command
    ansible_command(controller, command)


def ansible_nova_create(controller):
    nova_virenv = autoscale_config.getConfig(conf_tag, "nova_virenv")
    nova_bin = autoscale_config.getConfig(conf_tag, "nova_bin")
    nova_action = 'create'
    image = autoscale_config.getConfig(conf_tag, "image")
    flavor = autoscale_config.getConfig(conf_tag, "create_flavor")
    net_id = autoscale_config.getConfig(conf_tag, "net_id")
    timestr = time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())
    nova_args = '--image %s \
                 --flavor %s \
                 --nic net-id= %s \
                 autoscale-%s' % (image, flavor, net_id, timestr)
    command = nova_virenv + ';' + nova_bin + ' ' + nova_action + ' ' + nova_args
    print command
    #ansible_command(controller, command)




if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'No tag specified!'
        sys.exit()
    #run_playbook("yml/info/process.yml")
    #run_adhoc("controller", "uptime | grep -ohe 'load average[s:][: ].*' | awk '{ print $4 }'")
    #la = run_adhoc("controller", "uptime")
    #import pdb;pdb.set_trace()
    conf_tag = sys.argv[1]
    ansible_hosts = autoscale_config.getConfig(conf_tag, "ansible_hosts")
    nova_controller = autoscale_config.getConfig(conf_tag, "nova_controller")
    nova_action = autoscale_config.getConfig(conf_tag, "nova_action")

    la_vn = run_adhoc(ansible_hosts, "uptime | grep -ohe 'load average[s:][: ].*'; grep 'model name' /proc/cpuinfo | wc -l")
    for x in la_vn.host_ok:
        ret = parse_la_vn(x['result']._result['stdout'])
        print ret
        if ret['la'][2] <= ret['vn']*3/4:
            print nova_action
            if nova_action == 'resize':
                ansible_nova_resize(nova_controller, x['ip'])
            else:
                ansible_nova_create(nova_controller)
        break;


    #nova = run_adhoc("controller", "pwd")
    #nova = run_adhoc("controller", "source /root/openrc")
    #for x in nova.host_failed:
    #    print x['ip'], x['task'], x['result']._result
    #for x in nova.host_ok:
    #    print x['ip'], x['task'], x['result']._result

