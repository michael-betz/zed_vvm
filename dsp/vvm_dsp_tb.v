`timescale 1 ns / 1 ns

module vvm_dsp_tb;
    localparam pi = 3.141592653589793;
    // ADC sampling clock f_s [Hz]
    // chosen for f_RF / f_ADC ~ 4.25
    localparam F_ADC = 117600000;
    // Simulated clock period in [ns]
    localparam T_ADC = 1000000000 / F_ADC;
    reg clk_adc = 1;
    integer f;
    always #(T_ADC / 2) begin
        clk_adc = ~clk_adc;
    end

    // ------------------------------------------------------------------------
    //  Simulate ADC signals
    // ------------------------------------------------------------------------
    // ALS MO reference and phase shifted signal under test
    // localparam F_REF = 499600000;  // [Hz]
    localparam F_REF = 25000000;  // [Hz]
    localparam OMEGA_REF = (1.0 / F_ADC * 2.0 * pi * F_REF);
    // Phase shift between adc_ref and adc_a
    localparam THETA_A = 0;
    localparam THETA_B = 2.0 / 3 * pi;
    localparam THETA_C = 4.0 / 3 * pi;

    // As we undersample and operate on a non-inverted nyquist band,
    // signal will appear at:
    localparam F_REF_US = ((1.0 * F_REF / F_ADC) % 1) * F_ADC;

    reg signed [13:0] adc_ref = 14'h0;
    reg signed [13:0] adc_a = 14'h0;
    reg signed [13:0] adc_b = 14'h0;
    reg signed [13:0] adc_c = 14'h0;

    // Deserialize one of the channels after the down-converter
    // for plotting
    wire strobe_out;
    parameter W_CORDIC = 21;
    wire signed [W_CORDIC - 1: 0] adc_ref_dc_i;
    wire signed [W_CORDIC - 1:0] adc_ref_dc_q;
    grab_channels #(
        .DW     (W_CORDIC)
    ) gc_inst (
        .clk        (clk_adc),
        .stream_in  (dsp_inst.result_iq),
        .strobe_in  (dsp_inst.result_strobe),

        .strobe_out (strobe_out),
        .i_out0     (adc_ref_dc_i),
        .q_out0     (adc_ref_dc_q)
    );

    integer sample_cnt = 0;
    always @(posedge clk_adc) begin
        sample_cnt <= sample_cnt + 1;
        adc_ref <= ((1 << 13) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF);
        adc_a <= ((1 << 13) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF + THETA_A);
        adc_b <= ((1 << 13) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF + THETA_B);
        adc_c <= ((1 << 13) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF + THETA_C);
        if (!reset) begin
            $fwrite(
                f,
                "%d, %d, %d, %d, %d, %d\n",
                adc_ref, 0,
                dsp_inst.dds_o_cos, dsp_inst.dds_o_sin,
                strobe_out ? adc_ref_dc_i : 32'sh0,
                strobe_out ? adc_ref_dc_q : 32'sh0,
            );
        end
    end

    // ------------------------------------------------------------------------
    //  Handle the power on Reset
    // ------------------------------------------------------------------------
    reg reset = 1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("vvm_dsp.vcd");
            $dumpvars(7,vvm_dsp_tb);
        end
        f = $fopen("output.txt","w");
        $fwrite(f, "adc_ref, lo, adc_ref_dc\n");
        repeat (100) @(posedge clk_adc);
        reset <= 0;
        repeat (16000) @(posedge clk_adc);
        $fclose(f);
        $finish;
    end

    // ------------------------------------------------------------------------
    //  Instantiate the unit under test
    // ------------------------------------------------------------------------
    // IF at 20 kHz offset (rate at which phase_ref rolls over)
    localparam LO_FTW = 1.0 * (F_REF_US + 10000) / F_ADC * 2**32;
    wire [31:0] dds_ftw = LO_FTW;
    vvm_dsp #() dsp_inst (
        .sample_clk     (clk_adc),
        .sample_rst     (reset),

        .adcs           (adc_ref),
        .adcs_1         (adc_a),
        .adcs_2         (adc_b),
        .adcs_3         (adc_c),

        .ftw            (LO_FTW),
        .cic_period     (13'd100),
        .cic_shift      (4'd2),
        // decimation by factor of 1000 works fine with cic_shift = 9
        // bandwidth = 117.6 kHz

        .iir_shift      (6'd4)
        // Measurement smoothing factor
    );

endmodule
