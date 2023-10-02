{{ _header }}

parameter DELAY = {{ delay | default(0, true) }};

reg x;
wire en = clk & ~clkb;

assign out = x;

always@(en or in or rst)
    if (rst)
        x <= 1'b0;
    else
        if (en)
            x <= #DELAY in;
        else
            x <= x;
    
endmodule
