`timescale 1 ns / 1 ns

module phase_processor_tb;
    reg clk = 1;
    always #(10) begin
        clk = ~clk;
    end

    // ------------------------------------------------------------------------
    //  Handle the power on Reset
    // ------------------------------------------------------------------------
    reg reset = 1;
    reg strobe_in = 0;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("phase_processor.vcd");
            $dumpvars(12, phase_processor_tb);
        end
        repeat (99) @(posedge clk);
        reset <= 0;
        @(posedge clk);
        strobe_in <= 1;
        @(posedge clk);
        strobe_in <= 0;
        repeat (9) @(posedge clk);
        @(posedge clk);
        strobe_in <= 1;
        @(posedge clk);
        strobe_in <= 0;
        repeat (1600) @(posedge clk);
        $finish;
    end

    // ------------------------------------------------------------------------
    //  Instantiate the unit under test
    // ------------------------------------------------------------------------
    reg [20:0] mag_in = 21'h0;
    reg [21:0] phase_in = 22'h0;
    always @(posedge clk) begin
        phase_in <= phase_in + 22'h3;
        mag_in <= mag_in + 21'h1;
    end

    phase_processor dut(
        .sys_clk       (clk),
        .sys_rst       (reset),

        .mag_in        (mag_in),
        .phase_in      (phase_in),
        .strobe_in     (strobe_in),
        .mult_factors  (4'h3),
        .mult_factors_1(4'h4),
        .mult_factors_2(4'h5),

        .mags          (),
        .mags_1        (),
        .mags_2        (),
        .mags_3        (),
        .phases        (),
        .phases_1      (),
        .phases_2      (),
        .phases_3      (),
        .strobe_out    ()
    );

endmodule
