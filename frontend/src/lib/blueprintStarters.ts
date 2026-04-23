/**
 * Starter blueprints — curated YAML templates that new users can load
 * from ``/blueprints/new`` as a jumping-off point rather than staring
 * at a blank canvas.
 *
 * All models referenced here must exist in the ``device_templates``
 * catalog (see ``apps/templates/migrations/0002_seed_core_catalog.py``)
 * so the blueprint validator accepts them cleanly. Adding a starter
 * that uses a new model means adding that model to the catalog first.
 */

export type BlueprintStarter = {
  id: string;
  label: string;
  description: string;
  yaml: string;
};

const BLANK = `schema_version: uvl-blueprint/v1
name: untitled
description: ""
site:
  networks:
    - name: default
      vlan: 1
      subnet: 192.168.1.0/24
  devices: []
`;

const HOME = `schema_version: uvl-blueprint/v1
name: small-home
description: Typical home setup — router, switch, a couple of access points
site:
  networks:
    - name: default
      vlan: 1
      subnet: 192.168.1.0/24
    - name: iot
      vlan: 10
      subnet: 192.168.10.0/24
  wlans:
    - ssid: CV-Home
      network: default
      security: wpa2
    - ssid: CV-IoT
      network: iot
      security: wpa2
  devices:
    - hostname: gateway
      model: UDR
    - hostname: switch-core
      model: USW-Lite-8-PoE
      uplink: gateway
    - hostname: ap-upstairs
      model: U6-Pro
      uplink: switch-core
    - hostname: ap-downstairs
      model: U6-Lite
      uplink: switch-core
`;

const SMB = `schema_version: uvl-blueprint/v1
name: smb-office
description: Small business — gateway, core + access switch, five APs
site:
  networks:
    - name: staff
      vlan: 1
      subnet: 10.0.1.0/24
    - name: guest
      vlan: 20
      subnet: 10.0.20.0/24
    - name: voip
      vlan: 30
      subnet: 10.0.30.0/24
  wlans:
    - ssid: CV-Staff
      network: staff
      security: wpa3
    - ssid: CV-Guest
      network: guest
      security: wpa2
  devices:
    - hostname: gateway
      model: UDM-Pro
    - hostname: switch-core
      model: USW-Pro-24-PoE
      uplink: gateway
    - hostname: switch-access
      model: USW24P250
      uplink: switch-core
    - hostname: ap-reception
      model: U6-Pro
      uplink: switch-access
    - hostname: ap-openplan-a
      model: U6-Pro
      uplink: switch-access
    - hostname: ap-openplan-b
      model: U6-Pro
      uplink: switch-access
    - hostname: ap-boardroom
      model: U6-Enterprise
      uplink: switch-access
    - hostname: ap-kitchen
      model: U6-Lite
      uplink: switch-access
`;

const WAREHOUSE = `schema_version: uvl-blueprint/v1
name: warehouse-retail
description: Warehouse / retail — gateway, aggregation, three access switches, outdoor APs
site:
  networks:
    - name: corporate
      vlan: 1
      subnet: 10.10.0.0/24
    - name: scanner
      vlan: 40
      subnet: 10.10.40.0/24
    - name: guest
      vlan: 99
      subnet: 10.10.99.0/24
  wlans:
    - ssid: CV-Corporate
      network: corporate
      security: wpa3
    - ssid: CV-Scanners
      network: scanner
      security: wpa2
  devices:
    - hostname: gateway
      model: UDM-Pro-Max
    - hostname: switch-agg
      model: USW-Aggregation
      uplink: gateway
    - hostname: switch-zone-a
      model: USW-Pro-48-PoE
      uplink: switch-agg
    - hostname: switch-zone-b
      model: USW-Pro-48-PoE
      uplink: switch-agg
    - hostname: switch-loading
      model: USW-Pro-24-PoE
      uplink: switch-agg
    - hostname: ap-zone-a-1
      model: U6-LR
      uplink: switch-zone-a
    - hostname: ap-zone-a-2
      model: U6-LR
      uplink: switch-zone-a
    - hostname: ap-zone-b-1
      model: U6-LR
      uplink: switch-zone-b
    - hostname: ap-zone-b-2
      model: U6-LR
      uplink: switch-zone-b
    - hostname: ap-loading
      model: U7-Outdoor
      uplink: switch-loading
    - hostname: ap-yard
      model: U7-Outdoor
      uplink: switch-loading
`;

const CAMPUS = `schema_version: uvl-blueprint/v1
name: campus-multi-building
description: Campus — gateway, core, per-building access switches, U7 APs
site:
  networks:
    - name: staff
      vlan: 1
      subnet: 172.20.0.0/22
    - name: students
      vlan: 50
      subnet: 172.20.50.0/24
    - name: iot
      vlan: 60
      subnet: 172.20.60.0/24
  wlans:
    - ssid: CV-Staff
      network: staff
      security: wpa3
    - ssid: CV-Student
      network: students
      security: wpa2
    - ssid: CV-IoT
      network: iot
      security: wpa2
  devices:
    - hostname: gateway
      model: UXG-Max
    - hostname: switch-core
      model: USW-Enterprise-48-PoE
      uplink: gateway
    - hostname: switch-bldg-a
      model: USW-Enterprise-24-PoE
      uplink: switch-core
    - hostname: switch-bldg-b
      model: USW-Enterprise-24-PoE
      uplink: switch-core
    - hostname: switch-bldg-c
      model: USW-Pro-24-PoE
      uplink: switch-core
    - hostname: ap-a-lecture
      model: U7-Pro
      uplink: switch-bldg-a
    - hostname: ap-a-lab
      model: U7-Pro-Max
      uplink: switch-bldg-a
    - hostname: ap-b-library
      model: U7-Pro
      uplink: switch-bldg-b
    - hostname: ap-b-cafeteria
      model: U7-Pro
      uplink: switch-bldg-b
    - hostname: ap-c-admin
      model: U7-Pro
      uplink: switch-bldg-c
    - hostname: ap-c-reception
      model: U6-Pro
      uplink: switch-bldg-c
`;

export const BLUEPRINT_STARTERS: BlueprintStarter[] = [
  {
    id: "blank",
    label: "Blank",
    description: "Minimal skeleton with an empty devices list.",
    yaml: BLANK,
  },
  {
    id: "home",
    label: "Small home",
    description: "UDR gateway + 8-port switch + two U6 APs.",
    yaml: HOME,
  },
  {
    id: "smb",
    label: "SMB office",
    description: "UDM-Pro, core + access switch, five APs, staff/guest/VoIP VLANs.",
    yaml: SMB,
  },
  {
    id: "warehouse",
    label: "Warehouse / retail",
    description: "UDM-Pro-Max + aggregation + three access switches + outdoor APs.",
    yaml: WAREHOUSE,
  },
  {
    id: "campus",
    label: "Campus",
    description: "Gateway + core + per-building switches + U7 APs across three buildings.",
    yaml: CAMPUS,
  },
];

export function getStarter(id: string): BlueprintStarter | undefined {
  return BLUEPRINT_STARTERS.find((s) => s.id === id);
}
