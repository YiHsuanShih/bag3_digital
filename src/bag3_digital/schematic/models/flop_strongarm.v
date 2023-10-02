module {{_cell_name}}(
    //input
    input wire clk,
    input real inp,
    input real inn,
    input real vosp,
    input real vosn,
    //output
    output reg vmp,
    output reg vmn,
    output reg outp,
    output reg outn,
    output reg done
); 
parameter SENAMP_DEL = {{ delay | default(1.0, true) }};
parameter OFFSET_GAIN   = {{ offset_gain | default(0.25, true) }};

real inp_reg, inn_reg;
//Calculate ouput
always @(posedge clk) begin
    inp_reg <= #SENAMP_DEL inp;
    inn_reg <= #SENAMP_DEL inn;
    if ((inp+OFFSET_GAIN*vosp) >= (inn+OFFSET_GAIN*vosn)) begin
        vmp <= #SENAMP_DEL 1'd1;
        vmn <= #SENAMP_DEL 1'd0;
        outp <= #SENAMP_DEL 1'd1;
        outn <= #SENAMP_DEL 1'd0;
    end
    else begin
        vmp <= #SENAMP_DEL 1'd0;
        vmn <= #SENAMP_DEL 1'd1;
        outp <= #SENAMP_DEL 1'd0;
        outn <= #SENAMP_DEL 1'd1;
    end
end
always @(negedge clk) begin
    vmp <= 1'd1;
    vmn <= 1'd1;
end

assign done = vmp^vmn;

endmodule
