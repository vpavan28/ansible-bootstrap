# -*- coding: utf-8 -*-

# (c) 2017, Matt Martz <matt@sivel.net>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = '''
author: 'Matt Martz (@sivel)'
short_description: 'Deploys a VMware VM from an OVF or OVA file'
description:
- 'Deploys a VMware VM from an OVF or OVA file'
module: vmware_deploy_ovf
notes: []
options:
    datacenter:
        default: ha-datacenter
        description:
        - 'Datacenter to deploy to'
    datastore:
        default: datastore1
        description:
        - 'Datastore to deploy to'
    disk_provisioning:
        choices:
        - flat
        - eagerZeroedThick
        - monolithicSparse
        - twoGbMaxExtentSparse
        - twoGbMaxExtentFlat
        - thin
        - sparse
        - thick
        - seSparse
        - monolithicFlat
        default: thin
        description:
        - 'Disk provisioning type'
    name:
        description:
        - Name of the VM to work with.
        - VM names in vCenter are not necessarily unique, which may be problematic
    ovf_networks:
        default:
            VM Network: VM Network
        description:
        - 'C(key: value) mapping of OVF network name, to the vCenter network name'
    ovf:
        description:
        - 'Path to OVF or OVA file to deploy'
    power_on:
        default: true
        description:
        - 'Whether or not to power on the VM after creation'
        type: bool
    resource_pool:
        default: Resources
        description:
        - 'Resource Pool to deploy to'
    wait:
        default: true
        description:
        - 'Wait for the host to power on'
        type: bool
    wait_for_ip_address:
        default: false
        description:
        - Wait until vCenter detects an IP address for the VM.
        - This requires vmware-tools (vmtoolsd) to properly work after creation.
        type: bool
requirements:
    - pyvmomi
version_added: 2.5.0
extends_documentation_fragment: vmware.documentation
'''

EXAMPLES = '''
- vmware_deploy_ovf:
    hostname: esx.example.org
    username: root
    password: passw0rd
    ovf: /path/to/ubuntu-16.04-amd64.ovf
    wait_for_ip_address: true
'''

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

RETURN = '''
instance:
    description: metadata about the new virtualmachine
    returned: always
    type: dict
    sample: None
'''

import io
import os
import sys
import tarfile
import time
import traceback

import logging
logging.basicConfig(filename='/tmp/log_filename.txt', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
#logger = logging.getLogger()
#logger.setLevel(logging.DEBUG)
#
#formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#
#fh = logging.FileHandler('/tmp/log_filename.txt')
#fh.setLevel(logging.DEBUG)
#fh.setFormatter(formatter)
#logger.addHandler(fh)
#
#ch = logging.StreamHandler()
#ch.setLevel(logging.DEBUG)
#ch.setFormatter(formatter)
#logger.addHandler(ch)
#

from threading import Thread

from ansible.module_utils._text import to_native
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import string_types
from ansible.module_utils.urls import open_url
from ansible.module_utils.vmware import (HAS_PYVMOMI, connect_to_api, find_vm_by_name, find_datacenter_by_name, find_datastore_by_name,
                                         find_network_by_name, find_resource_pool_by_name, gather_vm_facts,
                                         vmware_argument_spec, set_vm_power_state, wait_for_task, wait_for_vm_ip, PyVmomi)
from ansible.modules.cloud.vmware.vmware_guest import (PyVmomiDeviceHelper, PyVmomiCache, PyVmomiHelper)
#from ansible.modules.cloud.vmware.vmware_guest import vmware_guest
#import ansible.modules.cloud.vmware.vmware_guest
try:
    from ansible.module_utils.vmware import vim
    from pyVmomi import vmodl
except ImportError:
    pass


def path_exists(value):
    if not isinstance(value, string_types):
        value = str(value)
    value = os.path.expanduser(os.path.expandvars(value))
    if not os.path.exists(value):
        raise ValueError('%s is not a valid path' % value)
    return value


class ProgressReader(io.FileIO):
    def __init__(self, name, mode='r', closefd=True):
        self.bytes_read = 0
        io.FileIO.__init__(self, name, mode=mode, closefd=closefd)

    def read(self, size=10240):
        chunk = io.FileIO.read(self, size)
        self.bytes_read += len(chunk)
        return chunk


class TarFileProgressReader(tarfile.ExFileObject):
    def __init__(self, *args):
        self.bytes_read = 0
        tarfile.ExFileObject.__init__(self, *args)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except:
            pass

    def read(self, size=10240):
        chunk = tarfile.ExFileObject.read(self, size)
        self.bytes_read += len(chunk)
        return chunk


class VMDKUploader(Thread):
    def __init__(self, vmdk, url, validate_certs=True, tarinfo=None, create=False):
        Thread.__init__(self)

        self.vmdk = vmdk

        if tarinfo:
            self.size = tarinfo.size
        else:
            self.size = os.stat(vmdk).st_size

        self.url = url
        self.validate_certs = validate_certs
        self.tarinfo = tarinfo

        self.f = None
        self.e = None
        self._create = create

    @property
    def bytes_read(self):
        try:
            return self.f.bytes_read
        except AttributeError:
            return 0

    def _request_opts(self):
        '''
        Requests for vmdk files differ from other file types. Build the request options here to handle that
        '''
        headers = {
            'Content-Length': self.size
        }

        if self._create:
            # Non-VMDK
            method = 'PUT'
            headers['Overwrite'] = 't'
        else:
            # VMDK
            method = 'POST'
            headers['Content-Type'] = 'application/x-vnd.vmware-streamVmdk'

        return {
            'method': method,
            'headers': headers,
        }

    def _open_url(self):
        open_url(self.url, data=self.f, validate_certs=self.validate_certs, **self._request_opts())

    def run(self):
        headers = {
            'Content-Type': 'application/x-vnd.vmware-streamVmdk',
            'Content-Length': self.size
        }

        if self.tarinfo:
            try:
                with TarFileProgressReader(self.vmdk, self.tarinfo) as self.f:
                    self._open_url()
            except Exception:
                self.e = sys.exc_info()
        else:
            try:
                with ProgressReader(self.vmdk, 'rb') as self.f:
                    self._open_url()
            except Exception:
                self.e = sys.exc_info()


class VMwareDeployOvf:
    def __init__(self, module):
        self.si = connect_to_api(module)
        self.module = module
        self.params = module.params

        self.datastore = None
        self.datacenter = None
        self.resource_pool = None
        self.network_mappings = []
        self.property_mappings = []

        self.ovf_descriptor = None
        self.tar = None

        self.lease = None
        self.import_spec = None
        self.entity = None

    def get_vm_obj(self):
        self.vm = find_vm_by_name(self.si, self.params['name'])
        return self.vm

    def get_objects(self):
        self.datastore = find_datastore_by_name(self.si, self.params['datastore'])
        if not self.datastore:
            self.module.fail_json(msg='%(datastore)s could not be located' % self.params)

        self.datacenter = find_datacenter_by_name(self.si, self.params['datacenter'])
        if not self.datacenter:
            self.module.fail_json(msg='%(datacenter)s could not be located' % self.params)

#        self.vm = find_vm_by_name(self.si, self.params['name'])
#        if not self.vm:
#            self.module.fail_json(msg='%(name)s could not be located' % self.params)

        self.resource_pool = find_resource_pool_by_name(self.si, self.params['resource_pool'])
        if not self.resource_pool:
            self.module.fail_json(msg='%(resource_pool)s could not be located' % self.params)

        for key, value in self.params['ovf_networks'].items():
            network = find_network_by_name(self.si, value)
            if not network:
                self.module.fail_json(msg='%(ovf_network)s could not be located' % self.params)
            network_mapping = vim.OvfManager.NetworkMapping()
            network_mapping.name = key
            network_mapping.network = network
            self.network_mappings.append(network_mapping)
       
        if self.params['property_map']:
            for key, value in self.params['property_map'].items():
                property_map = vim.KeyValue()
                property_map.key = key
                property_map.value = value
                self.property_mappings.append(property_map)


        return self.datastore, self.datacenter, self.resource_pool, self.network_mappings, self.property_mappings
        #return self.datastore, self.datacenter, self.vm, self.resource_pool, self.network_mappings
        #return self.datastore

    def get_ovf_descriptor(self):
        if tarfile.is_tarfile(self.params['ovf']):
            self.tar = tarfile.open(self.params['ovf'])
            ovf = None
            for candidate in self.tar.getmembers():
                dummy, ext = os.path.splitext(candidate.name)
                if ext.lower() == '.ovf':
                    ovf = candidate
                    break
            if not ovf:
                self.module.fail_json(msg='Could not locate OVF file in %(ovf)s' % self.params)

            self.ovf_descriptor = to_native(self.tar.extractfile(ovf).read())
        else:
            with open(self.params['ovf']) as f:
                self.ovf_descriptor = f.read()

        return self.ovf_descriptor

    def get_lease(self):
        datastore, datacenter, resource_pool, network_mappings, property_mappings = self.get_objects()

        params = {
            'diskProvisioning': self.params['disk_provisioning'],
        }
        if self.params['name']:
            params['entityName'] = self.params['name']
        if network_mappings:
            params['networkMapping'] = network_mappings
        if property_mappings:
            params['propertyMapping'] = property_mappings
        if self.params['deployment_option']:
            params['deploymentOption'] = self.params['deployment_option']

        spec_params = vim.OvfManager.CreateImportSpecParams(**params)

        ovf_descriptor = self.get_ovf_descriptor()

        self.import_spec = self.si.ovfManager.CreateImportSpec(
            ovf_descriptor,
            resource_pool,
            datastore,
            spec_params
        )

        #self.lease = resource_pool.ImportVApp(
        #    self.import_spec.importSpec,
        #    datacenter.vmFolder
        #)

        #joined_errors = '. '.join(to_native(e.msg) for e in getattr(self.import_spec, 'error', []))
        errors = [to_native(e.msg) for e in getattr(self.import_spec, 'error', [])]
        spec_warnings = True
        if spec_warnings:
            errors.extend(
                (to_native(w.msg) for w in getattr(self.import_spec, 'warning', []))
            )    
        if errors:
            self.module.fail_json(
                msg='Failure validating OVF import spec: %s' % '. '.join(errors)
            )

        for warning in getattr(self.import_spec, 'warning', []):
            self.module.warn(to_native(warning.msg))

        try:
            self.lease = resource_pool.ImportVApp(
                self.import_spec.importSpec,
                datacenter.vmFolder
            )
        except vmodl.fault.SystemError as e:
            self.module.fail_json(
                msg='Failed to start import: %s' % to_native(e.msg)
            )

        while self.lease.state != vim.HttpNfcLease.State.ready:
            time.sleep(0.1)

        self.entity = self.lease.info.entity

        return self.lease, self.import_spec

    def upload(self):
        ovf_dir = os.path.dirname(self.params['ovf'])

        lease, import_spec = self.get_lease()

        uploaders = []


        for file_item in import_spec.fileItem:
            vmdk_post_url = None
            for device_url in lease.info.deviceUrl:
                if file_item.deviceId == device_url.importKey:
                    vmdk_post_url = device_url.url.replace('*', self.params['hostname'])
                    break

            if not vmdk_post_url:
                lease.HttpNfcLeaseAbort(
                    vmodl.fault.SystemError(reason='Failed to find deviceUrl for file %s' % file_item.path)
                )
                self.module.fail_json(
                    msg='Failed to find deviceUrl for file %s' % file_item.path
                )

            if self.tar:
                vmdk = self.tar
                try:
                    vmdk_tarinfo = self.tar.getmember(file_item.path)
                except KeyError:
                    lease.HttpNfcLeaseAbort(
                        vmodl.fault.SystemError(reason='Failed to find VMDK file %s in OVA' % file_item.path)
                    )
                    self.module.fail_json(
                        msg='Failed to find VMDK file %s in OVA' % file_item.path
                    )
            else:
                vmdk = os.path.join(ovf_dir, file_item.path)
                try:
                    path_exists(vmdk)
                except ValueError:
                    lease.HttpNfcLeaseAbort(
                        vmodl.fault.SystemError(reason='Failed to find VMDK file at %s' % vmdk)
                    )
                    self.module.fail_json(
                        msg='Failed to find VMDK file at %s' % vmdk
                    )
                vmdk_tarinfo = None

            uploaders.append(
                VMDKUploader(
                    vmdk,
                    vmdk_post_url,
                    self.params['validate_certs'],
                    tarinfo=vmdk_tarinfo,
                    create=file_item.create
                )
            )

        total_size = sum(u.size for u in uploaders)
        total_bytes_read = [0] * len(uploaders)
        for i, uploader in enumerate(uploaders):
            uploader.start()
            while uploader.is_alive():
                time.sleep(0.1)
                total_bytes_read[i] = uploader.bytes_read
                lease.HttpNfcLeaseProgress(int(100.0 * sum(total_bytes_read) / total_size))

            if uploader.e:
                lease.HttpNfcLeaseAbort(
                    vmodl.fault.SystemError(reason='%s' % to_native(uploader.e[1]))
                )
                self.module.fail_json(
                    msg='%s' % to_native(uploader.e[1]),
                    exception=''.join(traceback.format_tb(uploader.e[2]))
                )

    def complete(self):
        self.lease.HttpNfcLeaseComplete()

    def power_on(self):
        facts = {}
        if self.params['power_on']:
            task = self.entity.PowerOn()
            if self.params['wait']:
                try:
                    wait_for_task(task)
                except Exception,e:
                    self.module.fail_json(msg="Unable to PowerOn VM due to: %s" % to_native(e.message.msg))
                if task.info.state == 'error':
                    self.module.exit_json(msg="Error occured: %s" % to_native(task.info.error.msg))
                if self.params['wait_for_ip_address']:
                    _facts = wait_for_vm_ip(self.si, self.entity)
                    if not _facts:
                        self.module.fail_json(msg='Waiting for IP address timed out')
                    facts.update(_facts)

        if not facts:
            gather_vm_facts(self.si, self.entity)

        return facts

    def vm_power_on(self, vm_obj):
        facts = {}
        try:
            if self.params['power_on']:
                task = vm_obj.PowerOn()
                if self.params['wait']:
                    wait_for_task(task)
                    if self.params['wait_for_ip_address']:
                        _facts = wait_for_vm_ip(self.si, vm_obj)
                        if not _facts:
                            self.module.fail_json(msg='Waiting for IP address timed out')
                        facts.update(_facts)
        except Exception,e:
            module.fail_json(msg="Error received from vCenter" % e.message.msg)

        if not facts:
            gather_vm_facts(self.si, vm_obj)

        return facts

def custom_wait_for_task(task, module):
        try:
            wait_for_task(task)
        except Exception,e:
            module.fail_json(msg="Error received from vCenter" % e.message.msg)


def main():
    argument_spec = vmware_argument_spec()
    argument_spec.update(
        disk_provisioning=dict(type='str', default='thin',
                   choices=['flat', 'eagerZeroedThick', 'monolithicSparse', 'twoGbMaxExtentSparse', 'twoGbMaxExtentFlat', 'thin', 'sparse', 'thick',  'seSparse', 'monolithicFlat']),		
        name=dict(type='str', required=True),
        datacenter=dict(type='str', default='ha-datacenter'),
	datastore=dict(type='str', default='datastore1'),
        resource_pool=dict(type='str', default='Resources'),
	name_match=dict(type='str', choices=['first', 'last'], default='first'),
        networks=dict(type='list', default=[]),
        property_map=dict(type='dict', default={}),
        deployment_option=dict(type='str', default=None),
        uuid=dict(type='str'),
        folder=dict(type='str', default='/vm'),
        ovf_networks=dict(type='dict', default={'VM Network': 'VM Network'}),
	ovf=dict(type=path_exists),
        force=dict(type='bool', default=False),
	power_on=dict(type='bool', default=True),
	wait=dict(type='bool', default=True),
	wait_for_ip_address=dict(type='bool', default=True),
        guest_id=dict(type='str'),
        customization=dict(type='dict', default={}, no_log=True),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
    )

    if not module.params['power_on'] and (module.params['wait_for_ip_address'] or module.params['wait']):
        module.fail_json(msg='Cannot wait for VM when power_on=False')

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi python library not found')

    pyv_ovf = PyVmomi(module)
    pyv_vmomihelper = PyVmomiHelper(module)
    vm_ovf = pyv_ovf.get_vm()

    #vm_find = find_vm_by_name()
    #vm_ovf_helper = pyv_vmomihelper.get_vm()

    deploy_ovf = VMwareDeployOvf(module)
    deploy_ovf_PyVmH = PyVmomiHelper(module)

    vm = deploy_ovf.get_vm_obj()

    if vm:
        if vm.runtime.powerState != 'poweredOff':
            if module.params['force']:
                 set_vm_power_state(deploy_ovf_PyVmH.content, vm, 'poweredoff', module.params['force'])
            else:
                 module.fail_json(msg="Virtual Machine is Powered ON. Please Power Off the VM or use force to power it off before doing any customizations.")
        if module.params['networks'] or module.params['customization']:
            deploy_ovf_PyVmH.customize_vm(vm)
            myspec=deploy_ovf_PyVmH.customspec
            task=vm.CustomizeVM_Task(spec=myspec)
 
            facts = deploy_ovf.vm_power_on(vm)
  
            #wait_for_task(task)
            #task_power=vm.PowerOn()
            #wait_for_task(task_power)
            #facts=pyv_vmomihelper.gather_facts(vm)

            #cust=self.customspec
            #deploy_ovf_PyVmH.customize_vm(vm_obj=vm)
            #customspec = vim.vm.customization.Specification()
        else:
            module.fail_json(msg="VM already exists in the vCenter..! Use networks or customization parameters to customize the existing VM")
     
    else:
        #deploy_ovf = VMwareDeployOvf(module)

        deploy_ovf.upload()
        deploy_ovf.complete()

        #facts = deploy_ovf.power_on()

        if module.params['networks'] or module.params['customization']:
            vm_deploy = deploy_ovf.get_vm_obj()
            deploy_ovf_PyVmH.customize_vm(vm_deploy)
            myspec=deploy_ovf_PyVmH.customspec
            task=vm_deploy.CustomizeVM_Task(spec=myspec)

#            custom_wait_for_task(task, module)
 
            try:
                wait_for_task(task) 
            except Exception,e:
                module.fail_json(msg="Error:%s" % e.message.msg)
            if task.info.state == 'error':
                module.fail_json(msg="Error occured: %s" % to_native(task.info.error.msg))

            try:
               facts = deploy_ovf.vm_power_on(vm_deploy)
            except Esxeption,e:
               module.fail_json(msg="Error from vCenter: %s" % e.message.msg)

            #wait_for_task(task)
            #facts = deploy_ovf.power_on()
            #module.exit_json(instance=facts)
        else:
            try:
                facts = deploy_ovf.power_on()
            except Exception,e:
                module.fail_json(msg="Error: %s" %(e.message.msg))
            #if task.info.state == 'error':
            #    module.exit_json(msg="Error occured: %s" % to_native(task.info.error.msg))

    #for item in datacenter.items():
    #    vobj = item[0]

    #if vm_ovf:
    #    test1 = pyv_ovf.get_vm()
    #else:
    #    module.fail_json(msg="VM doesn't exists invcenter..!")

    #if vm_ovf_helper:
    #    test2 = pyv_vmomihelper.get_vm()
    #else:
    #    module.fail_json(msg="VM doesn't exists invcenter..!")

    #deploy_ovf = VMwareDeployOvf(module)
    #deploy_ovf.upload()
    #deploy_ovf.complete()
    #facts = deploy_ovf.power_on()

    #customize = pyv_vmomihelper.customize_vm(getobj vm instalce object)

    #module.exit_json(instance=pyv_vmomihelper.gather_facts(vm))
    module.exit_json(instance=facts)


if __name__ == '__main__':
    main()
