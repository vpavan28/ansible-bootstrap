#### How to use this role.

> Deploy a VM from a ovf file (should also work for ova too, but haven't tested the functionality).

1. Deploy a VM , Poweron the deployed VM and wait for the PowerOn to be completed.

   * Please change the following values accordingly in `../roles/ovf_deploy/tasks/main.yml`

```yml
---
    - name: Deploying OVF template into vCenter
      vmware_deploy_ovf:
        hostname: '{{ vcenter }}'
        username: '{{ user_vc }}'
        password: '{{ pass_vc }}'
        datacenter: <DATACENTER_NAME in VCenter>
        datastore: <DATASTORE/DATASTORE_CLUSTER in VCenter>
        folder: '/vm'
        disk_provisioning: 'thin'
        name: 'Test-ASAv13'
        ovf: '/tmp/asav982/asav-vi.ovf'
        ovf_networks:
          Management0-0: pg104-host-mgmt
          GigabitEthernet0-0: pg103-host-pxe
          GigabitEthernet0-1: pg103-host-pxe
          GigabitEthernet0-2: pg103-host-pxe
          GigabitEthernet0-3: pg103-host-pxe
          GigabitEthernet0-4: pg103-host-pxe
          GigabitEthernet0-5: pg103-host-pxe
          GigabitEthernet0-6: pg103-host-pxe
          GigabitEthernet0-7: pg103-host-pxe
          GigabitEthernet0-8: pg103-host-pxe
#        deployment_option: 'ASAv50'
#        property_map:
          #'Configuration': ASAv10
#          'HARole': Standalone
          #'DeploymentOptionSection': ASAv10
          #'Deployment Type': HARole
#'        networks:
#          - name: Management0-0
#            ip: 10.7.20.121
#            gateway: 10.7.20.1
#            netmask: 255.255.255.0
#            device_type: vmxnet3
#          - name: dPG105-host-iscsi2
#            ip: 10.7.22.172
#            gateway: 10.7.22.1
#            netmask: 255.255.255.0
#            device_type: vmxnet3
#        customization:
#          domain: encore-oam.com
#          dns_servers:
#          - 10.231.0.101
#          - 10.231.0.103
        power_on: true
        force: false
        wait: true
        wait_for_ip_address: false
        validate_certs: False
      delegate_to: localhost

```
> ### Options available for using this module are :

```yml
options:
    hostname: '{{ vcenter }}'
    username: '{{ user_vc }}'
    password: '{{ pass_vc }}'
    datacenter: '<DATACENTER_NAME in VCenter>'
        #default: ha-datacenter
        #description: 'Datacenter to deploy to'
    datastore: '<DATASTORE/DATASTORE_CLUSTER in VCenter>'
        #default: datastore1
        #description: 'Datastore to deploy to'
    disk_provisioning: 'thin'
        #Available choices are:
            #- flat
            #- eagerZeroedThick
            #- monolithicSparse
            #- twoGbMaxExtentSparse
            #- twoGbMaxExtentFlat
            #- thin
            #- sparse
            #- thick
            #- seSparse
            #- monolithicFlat
        #default: thin
        #description: 'Disk provisioning type'
    name: '<NAME of the VM to be in VCenter'
        #description: Name of the VM to work with. VM names in vCenter are not necessarily unique, which may be problematic
    ovf_networks:
       <Network Name in OVF file>: <Portgroup you want to assign in VCenter>
       <Network Name in OVF file>: <Portgroup you want to assign in VCenter>
       <Network Name in OVF file>: <Portgroup you want to assign in VCenter>
        #default: VM Network: VM Network
        #description:C type (key: value) mapping of OVF network name, to the vCenter network name'
    ovf: 'Absolute Path to the OVF file location'
        #description:'Absolute Path to OVF or OVA file to deploy'
    resource_pool: '<RESOURCEPOOL you want to Deploy to in VCenter>'
        #default: Resources
        #description: 'Resource Pool to deploy to'
    power_on: 'true or false'
        #default: true
        #description: 'Whether or not to power on the VM after creation. (type: bool)
    wait: 'true or false'
        #default: true
        #description: 'Wait for the VM to power on' (type: bool)
    wait_for_ip_address: 'true or false'
        #default: false
        #description: Wait until vCenter detects an IP address for the VM. (type: bool)
        #This requires vmware-tools (vmtoolsd) to properly work after creation.
    deployment_option: '<CONFIGURATION_VALUE in OVF>'
        #default: If empty, the default option is chosen from the OVF Descriptor.
        #description: The key of the chosen deployment option if at all exists in the OVF file. Depending on this
        #configuration VM will get it's resources if PRE-DEFINED in the OVF.
    property_map:
       <Property KEY Name from  OVF>: <Proparty VALUE from OVF>
       <Property KEY Name from  OVF>: <Proparty VALUE from OVF>
       <Property KEY Name from  OVF>: <Proparty VALUE from OVF>
          #'Configuration': ASAv10
#          'HARole': Standalone
          #'DeploymentOptionSection': ASAv10
          #'Deployment Type': HARole
#'        networks:
#          - name: Management0-0
#            ip: 10.7.20.121
#            gateway: 10.7.20.1
#            netmask: 255.255.255.0
#            device_type: vmxnet3
#          - name: dPG105-host-iscsi2
#            ip: 10.7.22.172
#            gateway: 10.7.22.1
#            netmask: 255.255.255.0
#            device_type: vmxnet3
#        customization:
#          domain: encore-oam.com
#          dns_servers:
#          - 10.231.0.101
#          - 10.231.0.103
     
```

