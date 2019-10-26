// 4 channel digital down converter for the vector voltmeter

module ddc #(
    parameter dw         = 16, // ADC input width
    parameter oscw       = 18, // Oscillator input width
    parameter davr       = 3,  // Guard bits at output of mixer
    parameter ow         = 28, // second-order CIC data path width
    parameter rw         = 20, // result width out of ccfilt
    parameter pcw        = 13, // cic_period counter width
    parameter shift_base = 7,  // see ccfilt.v
    parameter nadc       = 8
) (
    input                       clk,
    input                       reset,
    input         [nadc*dw-1:0] adcs,   // each dw-wide adc data is signed
    input signed  [oscw-1:0]    cosa,
    input signed  [oscw-1:0]    sina,

    // Presumably host-settable parameters in the clk domain
    input         [pcw-1:0]     cic_period,  // expected values 33 to 33*128
    input         [3:0]         cic_shift,   // expected values 7 to 15

    //iq stream output:
    // <strobe_cc high> I0, Q0, I1, Q1, I2, Q2, I3, Q3 <strobe_cc low>
    output signed [rw-1:0]      result_iq,
    output                      strobe_cc
);

    // width [bits] of each I, Q channel at the mixer output
    localparam MIX_W = (8'h00 + dw + davr);

    // ---------------------
    // Instantiate Sampler
    // ---------------------
    wire cic_sample;

    multi_sampler #(
        .sample_period_wi (pcw))
    i_multi_sampler (
        .clk             (clk),
        .ext_trig        (1'b1),
        .sample_period   (cic_period),
        .dsample0_period (8'h1),
        .dsample1_period (8'h1),
        .dsample2_period (8'h1),
        .sample_out      (cic_sample),
        .dsample0_stb    (),
        .dsample1_stb    ()
    );

    // ---------------------
    // Instantiate mixers to create I and Q streams
    // ---------------------
    wire signed [nadc * MIX_W - 1: 0] mixout_i, mixout_q;

    iq_mixer_multichannel #(
        .NCHAN (nadc),
        .DWI   (dw),
        .DAVR  (davr),
        .DWLO  (oscw)
    ) i_iq_mixer_multichannel (
        .clk      (clk),
        .adc      (adcs),
        .cos      (cosa),
        .sin      (sina),
        .mixout_i (mixout_i),
        .mixout_q (mixout_q)
    );

    // ---------------------
    // Instantiate a shared CIC_MULTICHANNEL
    // ---------------------
    wire [MIX_W - 1: 0] zero = 0;
    cic_multichannel #(
        .n_chan        (nadc * 2),
        // DI parameters
        .di_dwi        (MIX_W),
        .di_rwi        (ow),
        .di_noise_bits (1), // NOTE: Setting to 1 to compensate for removed /2 from double_inte
        .cc_outw       (rw),
        .cc_halfband   (0),
        .cc_use_delay  (0),
        .cc_shift_base (shift_base)
    ) i_cic_multichannel_i (
        .clk           (clk),
        .reset         (reset),
        .stb_in        (1'b1),
        // make output order I0, Q0, I1, Q1, ...
        .d_in          ({
            mixout_q[3 * MIX_W +: MIX_W],
            mixout_i[3 * MIX_W +: MIX_W],
            mixout_q[2 * MIX_W +: MIX_W],
            mixout_i[2 * MIX_W +: MIX_W],
            mixout_q[1 * MIX_W +: MIX_W],
            mixout_i[1 * MIX_W +: MIX_W],
            mixout_q[0 * MIX_W +: MIX_W],
            mixout_i[0 * MIX_W +: MIX_W]
        }),
        .cic_sample    (cic_sample),
        .cc_sample     (1'b1),
        .cc_shift      (cic_shift),
        .di_stb_out    (), // Unused double-integrator tap
        .di_sr_out     (),
        .cc_stb_out    (strobe_cc),
        .cc_sr_out     (result_iq)
    );
endmodule
