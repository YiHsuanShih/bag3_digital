from typing import Any, Optional, Mapping, Type

from pybag.enum import MinLenMode, PinMode

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.template import TemplateDB
from bag.layout.routing.base import TrackID

from xbase.layout.mos.base import MOSBasePlaceInfo, MOSBase

from ..stdcells.memory import FlopCore
from .serNto1_fast import SerNto1Fast
from ...schematic.ser2Nto2_fast import bag3_digital__ser2Nto2_fast


class Ser2Nto2Fast(MOSBase):
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_digital__ser2Nto2_fast

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            pinfo='The MOSBasePlaceInfo object.',
            ridx_p='pch row index',
            ridx_n='nch row index',
            seg_dict='Dictionary of segments',
            ratio='Number of serialized inputs for each serNto1',
            export_nets='True to export intermediate nets',
            tap_sep_flop='Horizontal separation between column taps in number of flops. Default is ratio // 2.',
            is_rst_async='True if asynchronous rst input; False if synchronous rstb input. True by default',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            ridx_p=-1,
            ridx_n=0,
            export_nets=False,
            tap_sep_flop=-1,
            is_rst_async=True
        )

    def draw_layout(self) -> None:
        pinfo = MOSBasePlaceInfo.make_place_info(self.grid, self.params['pinfo'])
        self.draw_base(pinfo)

        ridx_p: int = self.params['ridx_p']
        ridx_n: int = self.params['ridx_n']
        seg_dict: Mapping[str, Any] = self.params['seg_dict']
        ratio: int = self.params['ratio']
        export_nets: bool = self.params['export_nets']
        tap_sep_flop: int = self.params['tap_sep_flop']
        if tap_sep_flop <= 0:
            tap_sep_flop = ratio >> 1
        is_rst_async: bool = self.params['is_rst_async']

        # make masters
        ser_params = dict(pinfo=pinfo, seg_dict=seg_dict['ser'], ridx_p=ridx_p, ridx_n=ridx_n, ratio=ratio,
                          tap_sep_flop=tap_sep_flop, is_rst_async=False)
        ser_master = self.new_template(SerNto1Fast, params=ser_params)
        ser_ncols = ser_master.num_cols
        ser_ntiles = ser_master.num_tile_rows

        if is_rst_async:
            ff_rst_params = dict(pinfo=pinfo, seg=seg_dict['ff'], resetable=True, rst_type='RESET')
            ff_rst_master = self.new_template(FlopCore, params=ff_rst_params)
            ff_rst_ncols = ff_rst_master.num_cols
            rst_sync_sch_params = dict(ff=ff_rst_master.sch_params)
        else:
            ff_rst_master = None
            ff_rst_ncols = 0
            rst_sync_sch_params = None

        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        xm_layer = vm_layer + 1
        ym_layer = xm_layer + 1
        xxm_layer = ym_layer + 1

        # --- Placement --- #
        cur_col = 0
        ser0 = self.add_tile(ser_master, 0, cur_col)
        ser1 = self.add_tile(ser_master, 2 * ser_ntiles - 1, cur_col)

        cur_col += ser_ncols + self.sub_sep_col
        inst_list = [ser0, ser1]

        if is_rst_async:
            rst_ff0 = self.add_tile(ff_rst_master, ser_ntiles - 1, cur_col + ff_rst_ncols, flip_lr=True)
            # extra blk_sp so that rst_ff1 output on vm_layer can go down to rst_ff0 input
            cur_col += ff_rst_ncols + self.min_sep_col
            rst_ff1 = self.add_tile(ff_rst_master, ser_ntiles, cur_col - ff_rst_ncols)
            inst_list.extend([rst_ff0, rst_ff1])
        else:
            rst_ff0 = rst_ff1 = None

        self.set_mos_size()

        # --- Routing --- #
        # supplies
        vdd_hm_list, vss_hm_list = [], []
        lower = 0
        upper = self.bound_box.xh
        for inst in inst_list:
            vdd_hm_list.append(inst.get_pin('VDD', layer=hm_layer))
            vss_hm_list.append(inst.get_pin('VSS', layer=hm_layer))
            lower = min(lower, vdd_hm_list[0].lower, vss_hm_list[-1].lower)
            upper = max(upper, vdd_hm_list[0].upper, vss_hm_list[-1].upper)
        vdd_hm = self.connect_wires(vdd_hm_list, lower=lower, upper=upper)[0]
        vss_hm = self.connect_wires(vss_hm_list, lower=lower, upper=upper)[0]
        vdd_xm = self.connect_wires([ser0.get_pin('VDD', layer=xm_layer), ser1.get_pin('VDD', layer=xm_layer)],
                                    lower=lower, upper=upper)[0]
        vdd_xxm = self.connect_wires([ser0.get_pin('VDD', layer=xxm_layer), ser1.get_pin('VDD', layer=xxm_layer)],
                                     lower=lower, upper=upper)[0]
        vss_xm = self.connect_wires([ser0.get_pin('VSS', layer=xm_layer), ser1.get_pin('VSS', layer=xm_layer)],
                                    lower=lower, upper=upper)[0]
        vss_xxm = self.connect_wires([ser0.get_pin('VSS', layer=xxm_layer), ser1.get_pin('VSS', layer=xxm_layer)],
                                     lower=lower, upper=upper)[0]
        self.add_pin('VDD', [vdd_hm, vdd_xm, vdd_xxm])
        self.add_pin('VSS', [vss_hm, vss_xm, vss_xxm])
        vdd_ym = self.connect_wires(ser0.get_all_port_pins('VDD_ym') + ser1.get_all_port_pins('VDD_ym'))
        vss_ym = self.connect_wires(ser0.get_all_port_pins('VSS_ym') + ser1.get_all_port_pins('VSS_ym'))
        self.add_pin('VDD_ym', vdd_ym, hide=True)
        self.add_pin('VSS_ym', vss_ym, hide=True)

        # dout<0> and dout<1>
        self.add_pin('dout<0>', ser0.get_pin('dout'), mode=PinMode.UPPER)
        self.add_pin('dout<1>', ser1.get_pin('dout'), mode=PinMode.UPPER)

        # clk and clkb from tristate inverters
        self.add_pin('clk_buf<0>', ser0.get_pin('clk_buf', layer=xm_layer), hide=not export_nets)
        self.add_pin('clkb_buf<0>', ser0.get_pin('clkb_buf', layer=xm_layer), hide=not export_nets)

        self.add_pin('clk_buf<1>', ser1.get_pin('clkb_buf', layer=xm_layer), hide=not export_nets)
        self.add_pin('clkb_buf<1>', ser1.get_pin('clk_buf', layer=xm_layer), hide=not export_nets)

        clk_list = [ser0.get_pin('clk'), ser1.get_pin('clkb')]
        clkb_list = [ser1.get_pin('clk'), ser0.get_pin('clkb')]

        # rstb_sync
        rstb_sync_xm = [ser0.get_pin('rstb_sync_in'), ser1.get_pin('rstb_sync_in')]

        if is_rst_async:
            rstb_sync = self.connect_to_track_wires(rstb_sync_xm, rst_ff0.get_pin('out'))
            self.add_pin('rstb_sync', rstb_sync, hide=not export_nets)

            # rst_ff1 output to rst_ff0 input
            rst_ff1_out = rst_ff1.get_pin('out')
            self.connect_to_track_wires(rst_ff0.get_pin('nin'), rst_ff1_out)

            # get xm_layer tracks
            xm_locs0 = self.tr_manager.spread_wires(xm_layer, ['sup', 'clk', 'sig', 'clk', 'clk', 'sup'],
                                                    lower=vss_xm[1].track_id.base_index,
                                                    upper=vdd_xm[1].track_id.base_index, sp_type=('clk', 'clk'))
            xm_locs1 = self.tr_manager.spread_wires(xm_layer, ['sup', 'clk', 'clk', 'sig', 'clk', 'sup'],
                                                    lower=vdd_xm[1].track_id.base_index,
                                                    upper=vss_xm[2].track_id.base_index, sp_type=('clk', 'clk'))

            # rst
            rst_vm_tid = self.tr_manager.get_next_track_obj(rst_ff1_out, 'sig', 'sig', 1)
            rst_vm = self.connect_to_tracks([rst_ff0.get_pin('prst'), rst_ff1.get_pin('prst')], rst_vm_tid)
            rst_ym = self.connect_via_stack(self.tr_manager, rst_vm, ym_layer,
                                            coord_list_o_override=[self.grid.track_to_coord(xm_layer, xm_locs0[2]),
                                                                   self.grid.track_to_coord(xm_layer, xm_locs1[-3])])
            self.add_pin('rst', rst_ym, mode=PinMode.LOWER)

            # clk and clkb from reset synchronizer flops
            w_clk_xm = self.tr_manager.get_width(xm_layer, 'clk')
            rst0_clk = self.connect_to_tracks(rst_ff0.get_pin('clk'), TrackID(xm_layer, xm_locs0[-2], w_clk_xm),
                                              min_len_mode=MinLenMode.MIDDLE)
            rst0_clkb = self.connect_to_tracks(rst_ff0.get_pin('clkb'), TrackID(xm_layer, xm_locs0[1], w_clk_xm),
                                               min_len_mode=MinLenMode.MIDDLE)
            rst1_clk = self.connect_to_tracks(rst_ff1.get_pin('clk'), TrackID(xm_layer, xm_locs1[1], w_clk_xm),
                                              min_len_mode=MinLenMode.MIDDLE)
            rst1_clkb_vm = rst_ff1.get_pin('clkb')
            rst1_clkb = self.connect_to_tracks(rst1_clkb_vm, TrackID(xm_layer, xm_locs1[-2], w_clk_xm),
                                               min_len_mode=MinLenMode.MIDDLE)

            # input of rst_ff1
            _in_vm_tid = self.tr_manager.get_next_track_obj(rst1_clkb_vm, 'sig', 'sig', -1)
            self.connect_to_tracks([rst_ff1.get_pin('nin'), rst_ff1.get_pin('VDD')], _in_vm_tid)

            clk_list.extend([rst0_clk, rst1_clk])
            clkb_list.extend([rst0_clkb, rst1_clkb])

            # get ym_layer tracks
            _, ym_locs = self.tr_manager.place_wires(ym_layer, ['clk', 'clk', 'sig'], rst_ym.track_id.base_index, -1)
            ym_locs = ym_locs[:-1]
        else:
            self.add_pin('rstb_sync', rstb_sync_xm, connect=True)

            # get ym_layer tracks
            _, ym_locs = self.tr_manager.place_wires(ym_layer, ['sup', 'clk', 'clk'],
                                                     vdd_ym[-1][-1].track_id.base_index)
            ym_locs = ym_locs[1:]

        w_clk_ym = self.tr_manager.get_width(ym_layer, 'clk')

        # clk and clkb
        clk = self.connect_to_tracks(clk_list, TrackID(ym_layer, ym_locs[0], w_clk_ym))
        self.add_pin('clk', clk, mode=PinMode.LOWER)
        self.reexport(ser0.get_port('clk'))
        clkb = self.connect_to_tracks(clkb_list, TrackID(ym_layer, ym_locs[1], w_clk_ym))
        self.add_pin('clkb', clkb, mode=PinMode.LOWER)
        self.reexport(ser1.get_port('clk'), net_name='clkb')

        # clk_div
        self.connect_wires([ser0.get_pin('clk_div', layer=vm_layer), ser1.get_pin('clk_div', layer=vm_layer)])
        clk_div_xm = self.connect_wires([ser0.get_pin('clk_div', layer=xm_layer),
                                         ser1.get_pin('clk_div', layer=xm_layer)])[0]
        _ym_tid = self.tr_manager.get_next_track_obj(vss_ym[-1][-1], 'sup', 'clk', -1)
        clk_div = self.connect_to_tracks(clk_div_xm, _ym_tid)
        self.add_pin('clk_div', clk_div_xm)
        self.add_pin('clk_div', clk_div, mode=PinMode.LOWER)

        # clk_div_buf from XSER1
        self.reexport(ser1.get_port('clk_div_buf'))

        # reexport wires on ym_layer for top level routing
        for idx in range(ratio):
            self.reexport(ser0.get_port(f'left_ym<{idx}>'))
            self.reexport(ser0.get_port(f'right_ym<{idx}>'))

        # inputs
        for idx in range(ratio):
            self.reexport(ser0.get_port(f'din<{idx}>'), net_name=f'din<{2 * idx}>')
            self.reexport(ser1.get_port(f'din<{idx}>'), net_name=f'din<{2 * idx + 1}>')

        # get schematic parameters
        self.sch_params = dict(
            ser=ser_master.sch_params,
            rst_sync=rst_sync_sch_params,
            export_nets=export_nets,
            is_rst_async=is_rst_async,
        )