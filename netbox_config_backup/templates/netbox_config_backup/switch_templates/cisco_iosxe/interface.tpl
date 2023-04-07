{% for vc_interfaces in queryset %}
interface {{interface.name}}{% if interface.description %}
 description {{interface.description}}{% endif %}
 {% if interface.mode == None %}
 {% if interface.vrf != None %}
 vrf member {{address.vrf.name}}{% endfor %}
 {% endif %}
 {% if interface.ip_addresses %}
 {% for address in interface.ip_addresses.all() if address.family == 4 %}
 ip address {{ address.address }}{% if address.role == "secondary" %} secondary{% endif %}
 {% endfor %}
 {% for address in interface.ip_addresses.all() if address.family == 6 %}
 ipv6 address {{ address.address }}
 {% endfor %}
 {% if
 hsrp version 2
 hsrp {{interface.untagged_vlan.vid}} ipv4
  priority 120
  preempt
  authentication md5 key-chain NCG-AUTH-HSRP
  timers 1 3{% for address in interface.ip_addresses.all() if address.family == 4 and address.role == "hsrp" %}
  ip {{ address.address | replace('/24','') }}{% endfor %}
 hsrp {{interface.untagged_vlan.vid}} ipv6
  priority 120
  preempt
  authentication md5 key-chain NCG-AUTH-HSRP
  timers 1 3{% for address in interface.ip_addresses.all() if address.family == 6 and address.role == "hsrp" %}
  ipv6 {{ address.address | replace('/64','') }}{% endfor %}
  {% endif %}
{% endfor %}