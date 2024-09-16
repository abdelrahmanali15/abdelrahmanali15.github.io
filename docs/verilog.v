// AMS PLL Project: Frequency Divider



`include "constants.vams"

`include "disciplines.vams"



module Divider(VIN,VOUT);



	output VOUT; voltage VOUT;	// output

	input VIN; voltage VIN;		// input (edge triggered)

	parameter real vh=1.2;		// output voltage in high state

	parameter real vl=0;		// output voltage in low state

	parameter real vth=0.6;	// threshold voltage at input

	parameter integer ratio=4 from [2:inf);	// divider ratio

	parameter real tt=10p from (0:inf);	// transition time of output signal

	parameter real td=0 from [0:inf);	// average delay from input to output


	real out_value=0;



	analog begin



    	@(cross(V(VIN) - vth, 1)) begin

			if (count==floor(ratio/2))

				out_value = vh;

			// *** add line here ***

				out_value = vl;

				// *** add line here ***

			end

			count = count + 1;			

   	end



 	   V(VOUT) <+ transition(out_value, td, tt);



	end

endmodule
