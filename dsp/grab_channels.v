// Extract the channels from a
// I, Q, I, Q ... stream
// stupidly trivial but useful

module grab_channels #(
    parameter DW = 16
) (
    input               clk,
    input      [DW-1:0] stream_in,
    input               strobe_in,

    output reg [DW-1:0] i_out0,
    output reg [DW-1:0] q_out0,
    output reg [DW-1:0] i_out1,
    output reg [DW-1:0] q_out1,
    output reg [DW-1:0] i_out2,
    output reg [DW-1:0] q_out2,
    output reg [DW-1:0] i_out3,
    output reg [DW-1:0] q_out3,
    output reg          strobe_out
);

    reg [4:0] sig_cnt = 5'd0;
    reg [DW-1:0] stream_in_d;
    always @(posedge clk) begin
        strobe_out <= 0;
        stream_in_d <= stream_in;
        sig_cnt <= 5'd0;
        if (strobe_in) begin
            sig_cnt <= sig_cnt + 1;
            case (sig_cnt)
                5'h1: begin
                    i_out0 <= stream_in_d;
                    q_out0 <= stream_in;
                end
                5'h3: begin
                    i_out1 <= stream_in_d;
                    q_out1 <= stream_in;
                end
                5'h5: begin
                    i_out2 <= stream_in_d;
                    q_out2 <= stream_in;
                end
                5'h7: begin
                    i_out3 <= stream_in_d;
                    q_out3 <= stream_in;
                    strobe_out <= 1;
                end
            endcase // sig_cnt
        end
    end

endmodule
