#ifndef NEXTION_INTERFACE_H
#define NEXTION_INTERFACE_H

#include "DynamicVariable.h"
#include "Arduino.h"

namespace nex
{
    enum type
    {
        TEXT,
        BUTTON,
        PROGRESSBAR,
        GAUGE
    };
}

class NextionObject
{
    public:
        String id;
        String value;
        nex::type type;

        NextionObject(){id = "";value = "";type = nex::type::TEXT;}
        
        template <typename T>
        NextionObject(String id_, T value_, nex::type type_){
            setId(id_);
            setValue(value_);
            setType(type_);
        }

        void setId(String id_){id = id_;}
        void setType(nex::type type_){type = type_;}
        String getId(){return id;}
        String getValue(){return value;}
        nex::type getType(){return type;}

        template <typename T>
        void setValue(T value_){value = String(value_);}
};

class NextionInterface
{
    public:
        HardwareSerial* serial_i;
        dynvar::Container<NextionObject> objects;

        NextionInterface(HardwareSerial*);
        void init();
        void write(NextionObject);
        String listen();
        void endComm();
        
        template <typename T>
        void setObject(int idx_, String id_, T value_, nex::type type_)
        {
            if(idx_<objects.getSize())
            {
                objects.at(idx_).setId(id_);
                objects.at(idx_).setValue<T>(value_);
                objects.at(idx_).setType(type_);
            }
        }

        template <typename T>
        void updateObject(int idx_, T value_)
        {
            objects.at(idx_).setValue<T>(value_);
            write(objects.at(idx_));
        }

        template <typename T>
        void updateObject(String id_, T value_)
        {
            for(int i = 0;i<objects.getSize();i++)
            {
                if(objects.at(i).getId()==id_)
                {
                    updateObject<T>(i,value_);
                    break;
                }
            }
        }
};

NextionInterface::NextionInterface(HardwareSerial* serial_) : serial_i(serial_)
{
    objects = dynvar::Container<NextionObject>(10);
}

void NextionInterface::init()
{
    serial_i->begin(9600);
    serial_i->setTimeout(20);
}

void NextionInterface::endComm()
{
    serial_i->write(0xff);
    serial_i->write(0xff);
    serial_i->write(0xff);
}

void NextionInterface::write(NextionObject obj)
{
    String cmd = obj.getId();
    switch(obj.getType())
    {
        case nex::type::TEXT :
            cmd += ".txt=\"";
            cmd += obj.getValue() + "\"";
            break;
        case nex::type::GAUGE :
            cmd += ".val=";
            cmd += obj.getValue();
            break;
    }
    serial_i->print(cmd);
    endComm();
}

String NextionInterface::listen()
{
    const int buff_ln = 20;
    byte buff[buff_ln];
    char data_c[buff_ln];

    
    if(serial_i->available())
    {
        serial_i->readBytesUntil('\n',buff,buff_ln);
    }

    for(int i = 0;i<buff_ln;i++) data_c[i] = int(buff[i]);

    String sdata = String(data_c);
    
    if(sdata) return sdata;
    else return String("");
}

#endif