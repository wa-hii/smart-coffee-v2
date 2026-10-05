#include "FuzzyController.h"

FuzzyController::FuzzyController() : 
fuzzy_input(NULL),
fuzzy_output(NULL),
rules(NULL),
rules_list(NULL),
process_matrix(NULL),
input_count(0),
output_count(0),
rules_count(0)
{}

FuzzyController::~FuzzyController()
{
	if(process_matrix!=NULL) 
	{
		for(int i = 0;i<rules_count;i++)
		{
			//Free sub-array memory, int[]
			delete [] process_matrix[i];
		}
		//Free array memory, int*[]
		delete [] process_matrix;
	}
	
	delete [] fuzzy_input;
	delete [] fuzzy_output;
	delete [] rules_list;
	delete [] rules;
}

void FuzzyController::setInput(FuzzyVariable fvar)
{
	if(fuzzy_input==NULL)
	{
		fuzzy_input = new FuzzyVariable[input_count+1];
	}
	else
	{
		FuzzyVariable* temp_input = fuzzy_input;
		fuzzy_input = new FuzzyVariable[input_count+1];
		for(int i = 0;i<input_count;i++)
		{
			fuzzy_input[i] = temp_input[i];
		}
		delete [] temp_input;
	}
	fuzzy_input[input_count] = fvar;
	input_count++;
}

void FuzzyController::setOutput(FuzzyVariable fvar)
{
	if(fuzzy_output==NULL)
	{
		fuzzy_output = new FuzzyVariable[output_count+1];
	}
	else
	{
		FuzzyVariable* temp_output = fuzzy_output;
		fuzzy_output = new FuzzyVariable[output_count+1];
		for(int i = 0;i<output_count;i++)
		{
			fuzzy_output[i] = temp_output[i];
		}
		delete [] temp_output;
	}
	fuzzy_output[output_count] = fvar;
	output_count++;
}

void FuzzyController::setRules(std::string rule)
{
	//Parse string rule to rules_type
	rules_t* checked_rule = ruleCheck(rule);
	//NULL check
	if(checked_rule==NULL) return;
	if(rules_list==NULL)
	{
		rules_list = new std::string[rules_count+1];
		rules = new rules_t[rules_count+1];
	}
	else
	{
		std::string* temp_list = rules_list;
		rules_t* temp_rules = rules;
		rules_list = new std::string[rules_count+1];
		rules = new rules_t[rules_count+1];
		for(int i = 0;i<rules_count;i++)
		{
			rules_list[i] = temp_list[i];
			rules[i] = temp_rules[i];
		}
		
		delete [] temp_list;
		delete [] temp_rules;
	}
	rules_list[rules_count] = rule;
	rules[rules_count] = *checked_rule;
	rules_count++;
}

rules_t* FuzzyController::ruleCheck(std::string rule_)
{
	rules_t* rule = NULL;
	std::string* syntax;
	
	syntax = breakString(rule_);
	
	#if CHECK_RULE_SYNTAX
	std::string rule_syntax[] = {"IF","","IS","","THEN","","IS",""};
	for(int i = 0; i<rules_syntax_length; i+=2)
	{
		if(syntax[i]!=rule_syntax[i]) return NULL;
	}
	#endif
	rule = new rules_t(syntax[1],syntax[3],syntax[5],syntax[7]);
	return rule;
}

void FuzzyController::updateProcessMatrix()
{
	if(process_matrix!=NULL) 
	{
		for(int i = 0;i<rules_count;i++)
		{
			//Free sub-array memory, int[]
			delete [] process_matrix[i];
		}
		//Free array memory, int*[]
		delete [] process_matrix;
	}
	
	process_matrix = new int*[rules_count];
	
	for(int i = 0; i<rules_count; i++)
	{
		int input_pair[] = {-1,-1};
		int output_pair[] = {-1,-1};
		
		process_matrix[i] = new int[4];
		
		for(int j = 0;j<input_count;j++)
		{
			if(fuzzy_input[j].getId()==rules[i].getInputId())
			{
				input_pair[0] = j;
				input_pair[1] = fuzzy_input[j].checkMembership(rules[i].getInputValue());
			}
		}		
		for(int j = 0;j<output_count;j++)
		{
			if(fuzzy_output[j].getId()==rules[i].getOutputId())
			{
				output_pair[0] = j;
				output_pair[1] = fuzzy_output[j].checkMembership(rules[i].getOutputValue());
			}
		}
		process_matrix[i][0] = input_pair[0];
		process_matrix[i][1] = input_pair[1];
		process_matrix[i][2] = output_pair[0];
		process_matrix[i][3] = output_pair[1];
	}
}

void FuzzyController::process()
{
	if(input_count>1)
	{
		//Reset output variables
		for(int i = 0;i<rules_count;i++)
		{
			fuzzy_output[process_matrix[i][2]].getFuzzies()[process_matrix[i][3]-1].setValue(0.0);
		}
		
		for(int i = 0;i<rules_count;i++)
		{
			float input = fuzzy_input[process_matrix[i][0]].getFuzzies()[process_matrix[i][1]-1].getValue();
			float init_output = fuzzy_output[process_matrix[i][2]].getFuzzies()[process_matrix[i][3]-1].getValue();
			//Handle different input with same output, get mean value
			if(init_output!=0.0) input = (init_output + input)/2;
			fuzzy_output[process_matrix[i][2]].getFuzzies()[process_matrix[i][3]-1].setValue(input);
		}
	}
	else
	{
		//only have one I/O, faster
		for(int i = 0;i<rules_count;i++)
		{
			float input = fuzzy_input[process_matrix[i][0]].getFuzzies()[process_matrix[i][1]-1].getValue();
			fuzzy_output[process_matrix[i][2]].getFuzzies()[process_matrix[i][3]-1].setValue(input);
		}	
	}
}