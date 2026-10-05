#include "FuzzyController.h"
#include <iostream>

int main(int argc, char**argv)
{		
	/**
	Variable:
	 dT
	 
	Membership:
	 High
	 Low
	 
	**/
	
	FuzzyVariable dT("dT");
	float param_High[] = {1.0,-50.0,100.0,250.0,300.0};
	float param_Low[] = {1.0,-300,-250.0,-100.0,50.0};
	dT.setMembership("High",TRAPEZOIDAL,OPEN_HIGH,param_High);
	dT.setMembership("Low",TRAPEZOIDAL,OPEN_LOW,param_Low);
	
	/**
	Variable:
	 Valve
	 
	Membership :
	 Open
	 Closed
	
	**/
	
	FuzzyVariable Valve("Valve");
	float param_Open[] = {1.0,0.0,100.0,200.0};
	float param_Close[] = {1.0,-100.0,0.0,100.0};
	Valve.setMembership("Open",TRIANGLE,CLOSED,param_Open);
	Valve.setMembership("Close",TRIANGLE,CLOSED,param_Close);
	
	/**
	 * Fuzzy Controller
	**/
	
	FuzzyController fC;
	//System Input
	fC.setInput(dT);
	//System Output
	fC.setOutput(Valve);
	//Rules
	fC.setRules("IF dT IS High THEN Valve IS Open ");
	fC.setRules("IF dT IS Low THEN Valve IS Close ");
	//Update Process Matrix
	fC.updateProcessMatrix();
	
	while(1)
	{
		float new_input_data;
		std::cin>>new_input_data;
		dT.Fuzzyfication(new_input_data);
		fC.process();
		float output_data = Valve.Defuzzyfication();
		if(output_data==-1) std::cout<<"Cant defuzz! Division by zero!"<<std::endl;
		else std::cout<<output_data<<std::endl;
	}
	return 0;
}