{{ _header }}

parameter DELAY = {{ delay | default(0, true) }};

reg x;
wire en = clk & ~clkb;

assign out = x;

always@(en or in)
    if (en)
        x <= #DELAY in;
    else
        x <= x;
    
endmodule
