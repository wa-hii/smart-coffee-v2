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
	 vS
	 
	Membership:
	 Very Fast
	 Fast
	 Slow
	 Zero
	 
	**/
	
	FuzzyVariable vS("vS");
	float param_VFast[] = {1.0, 90.0, 150.0, 300.0};
	float param_Fast[] = {1.0, 50.0, 75.0, 100.0};
	float param_Slow[] = {1.0, 10.0, 45.0, 60.0};
	float param_Zero[] = {1.0, -10, 0, 20.0};
	vS.setMembership("VeryFast",TRIANGLE,CLOSED,param_VFast);
	vS.setMembership("Fast",TRIANGLE,CLOSED,param_Fast);
	vS.setMembership("Slow",TRIANGLE,CLOSED,param_Slow);
	vS.setMembership("Zero",TRIANGLE,CLOSED,param_Zero);
	
	/**
	Variable:
	 Valve
	 
	Membership :
	 Open
	 Closed
	
	**/
	
	FuzzyVariable Valve("Valve");
	float param_Open[] = {1.0,0.0,100.0,200.0};
	float param_HOpen[] = {1.0,35.0,50.0,85.0};
	float param_Close[] = {1.0,-100.0,0.0,100.0};
	Valve.setMembership("Open",TRIANGLE,CLOSED,param_Open);
	Valve.setMembership("HalfOpen",TRIANGLE,CLOSED,param_HOpen);
	Valve.setMembership("Close",TRIANGLE,CLOSED,param_Close);
	
	/**
	 * Fuzzy Controller
	**/
	
	FuzzyController fC;
	//System Input
	fC.setInput(dT);
	fC.setInput(vS);
	//System Output
	fC.setOutput(Valve);
	//Rules
	fC.setRules("IF dT IS High THEN Valve IS Open ");
	fC.setRules("IF dT IS Low THEN Valve IS Close ");
	fC.setRules("IF vS IS VeryFast THEN Valve IS CLose ");
	fC.setRules("IF vS IS Fast THEN Valve IS HalfOpen ");
	fC.setRules("IF vS IS Slow THEN Valve IS HalfOpen ");
	fC.setRules("IF vS IS Zero THEN Valve IS Open ");
	
	//Update Process Matrix
	fC.updateProcessMatrix();
	
	while(1)
	{
		float dT_input_data,vS_input_data;
		std::cin>>dT_input_data>>vS_input_data;
		dT.Fuzzyfication(dT_input_data);
		vS.Fuzzyfication(vS_input_data);
		fC.process();
		
		float output_data = Valve.Defuzzyfication();
		if(output_data==-1) std::cout<<"Cant defuzz! Division by zero!"<<std::endl;
		else std::cout<<output_data<<std::endl;
	}
	return 0;
}