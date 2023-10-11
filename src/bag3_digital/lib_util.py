from typing import Dict, Any, List, Optional, Tuple
from jinja2 import Template
from pybag.enum import TermType
from bag3_serdes_rx.util import get_bus_width, get_bus_base

def get_lib_io(pins: Dict[str, TermType]) -> Tuple[List[str], List[str]]:
    input_pins = []
    output_pins = []
    for pin_name, pin_type in pins.items():
        if pin_type == TermType.input:
            input_pins.append(pin_name)
        elif pin_type == TermType.output:
            output_pins.append(pin_name)
    
    return input_pins, output_pins

def generate_lib_yaml(lib_params: Dict[str, Any]) -> None:
    template_path=lib_params['template_path']
    lib_path=lib_params['lib_path']
    with open(template_path) as f:
        template = Template(f.read())
    j2_template = template.render(lib_params)

    with open(lib_path, "w") as fh:
        fh.write(j2_template)
    print(f'lib_yaml file: {lib_path}')

def get_test_pins(test_pin_base: List[str], output_pins: List[str]) -> List[str]:
    test_pins = []
    for pin in output_pins:
        pin_base = get_bus_base(pin)
        pin_width = get_bus_width(pin)
        if pin_base in test_pin_base:
            for idx in range(pin_width):
                test_pins.append(f'{pin_base}<{idx}>')
    return test_pins


