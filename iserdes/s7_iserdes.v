/* Machine-generated using Migen */
module s7_iserdes(
	input dco_p,
	input dco_n,
	input lvds_data_p,
	input lvds_data_n,
	input bitslip,
	input id_inc,
	input id_dec,
	output [4:0] id_value,
	output reg [7:0] data_outs,
	input sys_clk,
	input sys_rst
);

wire sample_clk;
wire sample_rst;
reg init_running = 1'd1;
wire dco;
wire dco_delay;
wire dco_delay_2;
wire id_CE;
reg bufmr_ce = 1'd0;
reg bufr_clr = 1'd1;
reg [4:0] counter = 5'd0;
wire io_clk;
wire bufr_0_clk;
wire d_i;
reg rst_iserdes_ = 1'd0;
reg bitslip_ = 1'd0;
wire [7:0] d_o_;
wire rst_meta;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign id_CE = (id_inc ^ id_dec);
assign sample_clk = bufr_0_clk;

always @(posedge bufr_0_clk) begin
	rst_iserdes_ <= sample_rst;
	bitslip_ <= bitslip;
	data_outs <= d_o_;
end

always @(posedge sys_clk) begin
	if ((init_running & (counter == 1'd0))) begin
		bufr_clr <= 1'd1;
		bufmr_ce <= 1'd0;
	end
	if ((counter == 3'd4)) begin
		bufr_clr <= 1'd0;
	end
	if ((counter == 4'd8)) begin
		bufmr_ce <= 1'd1;
	end
	if ((counter == 5'd16)) begin
		init_running <= 1'd0;
	end
	if ((counter == 5'd16)) begin
		counter <= 1'd0;
	end else begin
		if ((counter != 1'd0)) begin
			counter <= (counter + 1'd1);
		end else begin
			if (init_running) begin
				counter <= 1'd1;
			end
		end
	end
	if (sys_rst) begin
		init_running <= 1'd1;
		bufmr_ce <= 1'd0;
		bufr_clr <= 1'd1;
		counter <= 5'd0;
	end
end

IDELAYE2 #(
	.DELAY_SRC("IDATAIN"),
	.HIGH_PERFORMANCE_MODE("TRUE"),
	.IDELAY_TYPE("VARIABLE"),
	.IDELAY_VALUE(4'd15),
	.REFCLK_FREQUENCY(200.0)
) IDELAYE2 (
	.C(sys_clk),
	.CE(id_CE),
	.CINVCTRL(1'd0),
	.CNTVALUEIN(5'd0),
	.DATAIN(1'd0),
	.IDATAIN(dco),
	.INC(id_inc),
	.LD(sys_rst),
	.LDPIPEEN(1'd0),
	.REGRST(1'd0),
	.CNTVALUEOUT(id_value),
	.DATAOUT(dco_delay)
);

BUFMRCE BUFMRCE(
	.CE(bufmr_ce),
	.I(dco_delay),
	.O(dco_delay_2)
);

BUFIO BUFIO(
	.I(dco_delay_2),
	.O(io_clk)
);

BUFR #(
	.BUFR_DIVIDE("4")
) BUFR (
	.CE(1'd1),
	.CLR(bufr_clr),
	.I(dco_delay_2),
	.O(bufr_0_clk)
);

ISERDESE2 #(
	.DATA_RATE("DDR"),
	.DATA_WIDTH(4'd8),
	.INTERFACE_TYPE("NETWORKING"),
	.IOBDELAY("NONE"),
	.NUM_CE(1'd1),
	.SERDES_MODE("MASTER")
) ISERDESE2 (
	.BITSLIP(bitslip_),
	.CE1(1'd1),
	.CE2(1'd1),
	.CLK(io_clk),
	.CLKB((~io_clk)),
	.CLKDIV(bufr_0_clk),
	.D(d_i),
	.DDLY(1'd0),
	.DYNCLKDIVSEL(1'd0),
	.DYNCLKSEL(1'd0),
	.RST(rst_iserdes_),
	.Q1(d_o_[0]),
	.Q2(d_o_[1]),
	.Q3(d_o_[2]),
	.Q4(d_o_[3]),
	.Q5(d_o_[4]),
	.Q6(d_o_[5]),
	.Q7(d_o_[6]),
	.Q8(d_o_[7])
);

IBUFDS IBUFDS(
	.I(dco_p),
	.IB(dco_n),
	.O(dco)
);

(* ars_ff1 = "true", async_reg = "true" *) FDPE #(
	.INIT(1'd1)
) FDPE (
	.C(sample_clk),
	.CE(1'd1),
	.D(1'd0),
	.PRE(init_running),
	.Q(rst_meta)
);

(* ars_ff2 = "true", async_reg = "true" *) FDPE #(
	.INIT(1'd1)
) FDPE_1 (
	.C(sample_clk),
	.CE(1'd1),
	.D(rst_meta),
	.PRE(init_running),
	.Q(sample_rst)
);

IBUFDS IBUFDS_1(
	.I(lvds_data_p),
	.IB(lvds_data_n),
	.O(d_i)
);

endmodule
