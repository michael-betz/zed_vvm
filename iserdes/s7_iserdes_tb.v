`timescale 1 ns / 1 ps

module s7_iserdes_tb;
    localparam real SYS_CLK_PERIOD = 1e9 / 100e6;    // Simulated clock period in [ns]
    localparam real FR_CLK_PERIOD = 1e9 / 125e6;     // SDR
    localparam real DCO_CLK_PERIOD = FR_CLK_PERIOD / 4.0; // DDR

    // Testpattern! LSB ends up on on LVDS lane B!
    reg [15:0] TP = 16'b0011110111011010;

    //------------------------------------------------------------------------
    // Clock and fake LVDS lanes generation
    //------------------------------------------------------------------------
    reg sys_clk = 1;
    reg fr_clk = 1;
    reg dco_clk_p = 0;
    reg out_a_p = 0;
    reg out_b_p = 0;
    always #(SYS_CLK_PERIOD / 2) sys_clk = ~sys_clk;
    always #(FR_CLK_PERIOD / 2) fr_clk = ~fr_clk;
    initial begin
        #(DCO_CLK_PERIOD / 4);
        forever #(DCO_CLK_PERIOD / 2) dco_clk_p = ~dco_clk_p;
    end
    reg [15:0] temp = 0;
    always begin
        // Craft 2 x 8 bit DDR signals according to timing diagram in LTC datasheet
        temp = TP;
        repeat (8) begin
            out_a_p = (temp & 16'h8000) != 0;
            temp = temp << 1;
            out_b_p = (temp & 16'h8000) != 0;
            temp = temp << 1;
            #(DCO_CLK_PERIOD / 2.0);
        end
    end

    //------------------------------------------------------------------------
    //  Handle the power on Reset
    //------------------------------------------------------------------------
    reg reset = 1;
    integer pass=1;
    initial begin
        repeat (15) @(posedge sys_clk);
        reset <= 0;
        #4000
        if(pass)
            $display("PASS");
        else
            $display("FAIL");
        $finish();
    end

    //------------------------------------------------------------------------
    // verify output data
    //------------------------------------------------------------------------
    wire sample_clk;
    integer cc = 0;
    always @(posedge sample_clk)
        cc <= cc + 1;
    reg bitslip = 0;
    wire [7:0] data_outs;
    wire [7:0] clk_data_out;
    wire [7:0] tp_a = {TP[15], TP[13], TP[11], TP[9], TP[7], TP[5], TP[3], TP[1]};
    wire [7:0] tp_b = {TP[14], TP[12], TP[10], TP[8], TP[6], TP[4], TP[2], TP[0]};
    initial begin
        wait (cc > 150);
        @ (posedge sample_clk);
        if (data_outs != tp_a) pass = 0;
        TP = ~TP;
        wait (cc > 160);
        @ (posedge sample_clk);
        if (data_outs != tp_a) pass = 0;
    end

    task bitslip_task;
        // Fires N bitslip events after everything is ready
        input [7:0] N;
        begin
            wait(cc > 100);
            while (N > 0) begin
                @ (posedge sample_clk);
                bitslip = 1;
                @ (posedge sample_clk);
                bitslip = 0;
                repeat (10)
                    @ (posedge sample_clk);
                N = N - 1;
            end
        end
    endtask

    initial
        if ($test$plusargs("vcd")) begin
            $dumpfile("s7_iserdes.vcd");
            $dumpvars(5, s7_iserdes_tb);
        end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    s7_iserdes dut (
        .dco_p          (dco_clk_p),
        .dco_n          (~dco_clk_p),
        .lvds_data_p    (out_a_p),
        .lvds_data_n    (~out_a_p),
        .sys_clk        (sys_clk),
        .sys_rst        (reset),
        .id_inc         (1'b0),
        .id_dec         (1'b0),
        .id_value       (),
        .bitslip        (1'b0),
        .data_outs      ()
    );

endmodule
