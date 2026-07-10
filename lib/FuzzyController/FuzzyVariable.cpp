#include "FuzzyVariable.h"

Triangle::Triangle(float height_,float l_side_, float mid_,float r_side_,shape_t type_=CLOSED) :
height(height_),
l_side(l_side_),
r_side(r_side_),
mid(mid_),
type(type_)
{}

float Triangle::getPoint(float side)
{
	switch(type)
	{
		case CLOSED:
			//check if side is in interval
			if(side<l_side || side>r_side) value = 0.0;
			//find point
			if(side==mid) value = height;
			else if(side<mid) value = ((side-l_side)/(mid-l_side))*height;
			else value = ((r_side-side)/(r_side-mid))*height;
			return value;
	}
}

Square::Square(float height_,float x_min_, float x_max_, shape_t type_=CLOSED) :
height(height_),
x_min(x_min_),
x_max(x_max_),
type(type_)
{}

float Square::getPoint(float x_value)
{
	switch(type)
	{
		case CLOSED:
			if(x_value>=x_min && x_value<=x_max) return height;
			else return 0.0;
			break;
		case OPEN_LOW:
			if(x_value<=x_max) return height;
			else return 0.0;
			break;
		case OPEN_HIGH:
			if(x_value>=x_min) return height;
			else return 0.0;
			break;
		default:
			return 0.0;
	}
}

Trapezoid::Trapezoid(float height_, float left_min_, float left_max_, float right_max_, float right_min_,shape_t type_=CLOSED) :
type(type_)
{
	//Allocate memory for membership functions
	mid_side = new Square(height_,left_max_,right_max_,type);
	left_side = new Triangle(height_,left_min_,left_max_,right_max_);
	right_side = new Triangle(height_,left_max_,right_max_,right_min_);
}

Trapezoid::~Trapezoid()
{
	//Free memory
	delete mid_side;
	delete left_side;
	delete right_side;
}

float Trapezoid::getPoint(float x_value)
{
	switch(type)
	{
		case CLOSED:
			if(x_value<mid_side->getMin()) return left_side->getPoint(x_value);
			else if(x_value>mid_side->getMax()) return right_side->getPoint(x_value);
			else if(x_value>=mid_side->getMin() && x_value<=mid_side->getMax()) return mid_side->getPoint(x_value);
			else return 0.0;
			break;
		case OPEN_LOW:
			if(x_value>mid_side->getMax()) return right_side->getPoint(x_value);
			else if(x_value<=mid_side->getMax()) return mid_side->getPoint(x_value);
			else return 0.0;
		case OPEN_HIGH:
			if(x_value<mid_side->getMin()) return left_side->getPoint(x_value);
			else if(x_value>=mid_side->getMin()) return mid_side->getPoint(x_value);
			else return 0.0;
			break;
	}
	
}

FuzzyVariable::FuzzyVariable(std::string id_) : 
id(id_),
membership(NULL),
type(NULL),
fuzzies(NULL),
counter(0) 
{}

FuzzyVariable::~FuzzyVariable()
{
	delete [] membership;
	delete [] type;
	delete [] fuzzies;
}

int FuzzyVariable::checkMembership(std::string id_)
{
	int check = 0;
	for(int i = 0;i<counter;i++)
	{
		if(fuzzies[i].getId()==id_) 
		{
			check = i+1;
			break;
		}
	}
	return check;
}
		
void FuzzyVariable::setMembership(std::string id, function_t func, shape_t shape, float* param)
{
	void* member_addr = NULL;
	
	switch(func)
	{
		case TRIANGLE:
			{
				Triangle* member = new Triangle(param[0],param[1],param[2],param[3],shape);
				member_addr = member;
			}
			break;
		case SQUARE:
			{
				Square* member = new Square(param[0],param[1],param[2],shape);
				member_addr = member;
			}
			break;
		case TRAPEZOIDAL:
			{
				Trapezoid* member = new Trapezoid(param[0],param[1],param[2],param[3],param[4],shape);
				member_addr = member;
			}
			break;
	}
	
	if(membership==NULL && type==NULL)
	{
		membership = new void*[counter+1];
		type = new function_t[counter+1];
		fuzzies = new fuzzy_t[counter+1];
		
		membership[counter] = member_addr;
		type[counter] = func;
		fuzzies[counter] = fuzzy_t(id,0.0);
		
		counter++;
	}
	else
	{
		void** temp_membership = membership;
		function_t* temp_type = type;
		fuzzy_t* temp_fuzzies = fuzzies;
		
		membership = new void*[counter+1];
		type = new function_t[counter+1];
		fuzzies = new fuzzy_t[counter+1];
		
		for(int i = 0; i<counter;i++)
		{
			membership[i] = temp_membership[i];
			type[i] = temp_type[i];
			fuzzies[i] = temp_fuzzies[i];
		}
		membership[counter] = member_addr;
		type[counter] = func;
		fuzzies[counter] = fuzzy_t(id,0.0);
		
		counter++;
		
		delete [] temp_membership;
		delete [] temp_type;
		delete [] temp_fuzzies;
	}
}

void FuzzyVariable::Fuzzyfication(float crisp_value)
{
	for(int i = 0; i<counter;i++)
	{
		float fuzzy_value;
		switch(type[i])
		{
			case TRIANGLE:
				{
					Triangle* membership_func = (Triangle*)membership[i];				
					fuzzy_value = membership_func->getPoint(crisp_value);
				}
				break;
			case SQUARE:
				{
					Square* membership_func = (Square*)membership[i];				
					fuzzy_value = membership_func->getPoint(crisp_value);
				}
				break;
			case TRAPEZOIDAL:
				{
					Trapezoid* membership_func = (Trapezoid*)membership[i];				
					fuzzy_value = membership_func->getPoint(crisp_value);
				}
				break;
		}
		fuzzies[i].setValue(fuzzy_value>0?fuzzy_value:0.0);
	}
}

float FuzzyVariable::Defuzzyfication()
{
	float weight_sum = 0.0;
	float weight_dn = 0.0;
	
	for(int i = 0; i<counter;i++)
	{
		float membership_value=0.0;
		float membership_weight=0.0;
		switch(type[i])
		{
			case TRIANGLE:
				Triangle* membership_func = (Triangle*)membership[i];
				membership_value = fuzzies[i].getValue();
				membership_weight = membership_func->getMid();
		}
		if(membership_value>0.0) 
		{
			weight_sum+=membership_value*membership_weight;
			weight_dn+=membership_value;
		}
	}
	
	if(weight_dn>0.0)
	{
		return weight_sum/weight_dn;
	}
	else
	{
		return -1;
	}
}