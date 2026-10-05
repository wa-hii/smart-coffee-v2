# the compiler: gcc for C program, define as g++ for C++
CC = g++

# compiler flags:
#  -g     - this flag adds debugging information to the executable file
#  -Wall  - this flag is used to turn on most compiler warnings
CFLAGS  = -g -Wall

# The build target 
#TARGET = example_one_in_out
TARGET = example_multi_io
LIB1 = FuzzyVariable
LIB2 = FuzzyController
LIB3 = Utils

RM = del /f

all: $(TARGET) clean

$(TARGET) : $(TARGET).o $(LIB1).o $(LIB2).o $(LIB3).o
	$(CC) $(CFLAGS) -o $(TARGET) $(TARGET).o $(LIB1).o $(LIB2).o $(LIB3).o
		
$(TARGET).o : $(TARGET).cpp $(LIB1).h $(LIB2).h
	$(CC) $(CFLAGS) -c $(TARGET).cpp

$(LIB1).o : $(LIB1).h

$(LIB3).o : $(LIB3).h

$(LIB2).o : $(LIB2).h $(LIB1).h $(LIB3).h

clean:
	$(RM) *.o