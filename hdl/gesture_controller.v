`timescale 1ns / 1ps
`default_nettype none

// Cycle-accurate model of arduino/gesture_controller/gesture_controller.ino
//
// Hardware (see README "Hardware" table and the Circuit Digest reference):
//   - A3144 hall sensor 1 -> Arduino pin 9   (hall_1)
//   - A3144 hall sensor 2 -> Arduino pin 10  (hall_2)
//   - HC-05 Bluetooth on SoftwareSerial 11/12 (rx_* / tx_*)
//   - LED on Arduino pin 13                  (led)
//
// Behaviour copied from the firmware:
//   - Whenever either hall sensor changes, one byte is written to the
//     Bluetooth module: (LOW,LOW)=1 (HIGH,LOW)=2 (LOW,HIGH)=3 (HIGH,HIGH)=4
//     and no byte is written while the combination is unchanged.
//   - An incoming 'y' turns the LED on, 'n' turns it off; any other byte
//     leaves the LED as it is.
module gesture_controller (
    input  wire       clk,
    input  wire       rst,       // synchronous, active high
    input  wire       hall_1,    // hall sensor 1 (Arduino pin 9)
    input  wire       hall_2,    // hall sensor 2 (Arduino pin 10)
    input  wire       rx_valid,  // byte available from the desktop app
    input  wire [7:0] rx_data,   // byte received over Bluetooth
    output reg  [7:0] tx_data,   // byte to send to the desktop app (1..4)
    output reg        tx_valid,  // single-cycle strobe with tx_data
    output reg        led        // Arduino pin 13
);

    reg [1:0] prev;

    always @(posedge clk) begin
        if (rst) begin
            // Globals in the sketch start at 0, so previous state is (LOW,LOW)
            prev     <= 2'b00;
            tx_data  <= 8'd0;
            tx_valid <= 1'b0;
            led      <= 1'b0;
        end else begin
            tx_valid <= 1'b0;

            // Send the new key combination whenever either hall sensor changes
            if ({hall_1, hall_2} != prev) begin
                prev     <= {hall_1, hall_2};
                tx_data  <= 8'd1 + {6'b00_0000, hall_2, hall_1};
                tx_valid <= 1'b1;
            end

            // 'y' / 'n' sent from the desktop app toggles the LED
            if (rx_valid) begin
                if (rx_data == "y")
                    led <= 1'b1;
                else if (rx_data == "n")
                    led <= 1'b0;
            end
        end
    end

endmodule

`default_nettype wire
