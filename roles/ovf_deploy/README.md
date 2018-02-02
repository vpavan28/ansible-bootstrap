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
        folder: '/<DATACENTER_NAME in VCenter>'
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
        deployment_option: 'ASAv50'
        property_map:
          'HARole': Standalone
#        networks:
#          - name: Management0-0
#            ip: 100.100.100.100
#            gateway: 100.7.20.1
#            netmask: 255.255.255.0
#            device_type: vmxnet3
#          - name: dPG105-host-iscsi2
#            ip: 10.100.22.172
#            gateway: 10.7.100.1
#            netmask: 255.255.255.0
#            device_type: vmxnet3
#        customization:
#          domain: encore-oam.com
#          dns_servers:
#          - 10.100.0.100
#          - 10.100.0.100
        force: false
        power_on: true
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
        #default: If no value is specified for an option, the  default value from the OVF descriptor is used.
        #description: The assignment of property values to the properties found in the descriptor, if at all defined in the OVF file.           #Depending on this you can choose Deploymnet Type etc. if PRE-DEFINED in the OVF.
    networks:
      - name: <Name of PortGroup which attached to the VM, should be equal to the one defined in ovf_networks above>
        ip: <IP ADDRESS which you want to assign to this interface>
        gateway: <GATEWAY>
        netmask: <SUBNET MASK 255.255.255.0 in this format>
        device_type: <Type of Virtual network devices (one of e1000, e1000e, pcnet32, vmxnet2, vmxnet3 (default: sriov)>
#          - name: dPG000-host-iscsi2
#            ip: 000.000.000.000
#            gateway: 000.000.000.000
#            netmask: 000.000.000.000
#            device_type: vmxnet3
        customization:
          hostname: <Computer hostname (default: name of the VM defined in Vcenter)>
          domain: <DOMAIN NAME>
          dns_servers:
          - <PRIMARY DNS>
          - <SECONDARY DNS>
     
```

