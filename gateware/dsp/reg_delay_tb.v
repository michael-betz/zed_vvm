`timescale 1 ns / 1 ns

module reg_delay_tb;
    reg clk = 1;
    always #(10) begin
        clk = ~clk;
    end

    // ------------------------------------------------------------------------
    //  Handle the power on Reset
    // ------------------------------------------------------------------------
    reg reset = 1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("reg_delay.vcd");
            $dumpvars(12,reg_delay_tb);
        end
        repeat (100) @(posedge clk);
        reset <= 0;
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

    reg_delay #(
        .dw(36),
        .len(3'h6)
    ) s1 (
        .clk(clk),
        .reset(1'b0),
        .gate(1'b1),
        .din(d_in),
        .dout()
    );

endmodule
