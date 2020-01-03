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
        repeat (100) @(posedge clk);
        reset <= 0;
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
    reg [35:0] d_in = 36'h0;

    always @(posedge clk) begin
        d_in <= d_in + 36'h1;
    end

    phase_processor dut(
        .sys_clk       (clk),
        .sys_rst       (reset),

        .mag_in        (21'h1),
        .phase_in      (22'h2),
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
