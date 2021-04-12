import tecnologias as t
import pyomo.environ as pyo
import pandas as pd
import numpy as np
from pyomo.opt import *

def modelo(bd):
    """
    Par aobtener el modelo de optimización
    """


    temperatura = bd[['Outside Temperature Impute C']]
    dates = bd[['hora', 'dia', 'mes']]
    radiacion = bd[['Solar Radiation Impute']].to_dict()["Solar Radiation Impute"]
    gi_pv = {i: round(radiacion[i],4) for i in range(len(radiacion))}
    carga = bd[['power Impute medida2 KWh']].to_dict()['power Impute medida2 KWh']
    load = {i: round(carga[i],4) for i in range(len(carga))}
    demanda_total = sum(load.values())
    # Potencia solar
    area_pv = 4.0
    eficiencia_pv = 0.18
    Npv = 1.0
    generacion_pv = {
        i: round(t.panel(area_pv, gi_pv[i], eficiencia_pv, Npv),4)
        for i in range(len(gi_pv))
    }
    ############################################################################################
    # Potencia Diésel
    # Datos diesel
    eficiencia_dg = 0.95
    Ndg = 2
    potencia = 1.0
    generacion_diesel = {
        i: round(t.diesel(eficiencia_dg, potencia, Ndg),4)
        for i in range(len(load))
    }
    ############################################################################################
    # Parámetros generales de restricción
    # Máxima LPSP pérmitida en porcentaje %
    max_lpsp = 0.2

    # Parámetro penalizada auxiliar
    val_aux_penalizado = potencia*Ndg
    val_aux_bateria = 0.1

    # % mínimo diésel
    per_min_dg = 0.30

    # Solo batería restricciones
    per_min_bat = 0.2  # Mínimo porcentaje permitido de la batería
    PB_rate_kW = 20  # Potencia nominal de la batería
    SOC_min = PB_rate_kW * per_min_bat  # Capacidad mínima de potencia permitida
    SOC_max = PB_rate_kW * 1  # Capacidad máxima permitida en la batería
    SOC_inicial = PB_rate_kW * 1 # Estado inicial de la batería en potenciá (100% del PB_rate_kW)
    max_ciclos_descarga = 1000  # Máximo número de ciclos de carga para la batería
    max_ciclos_carga = 1000  # Mínimo ciclos de carga para la batería
    self_discharge_coefficient = round(0.2 / 24, 4) # Coeficiente de autodescarga para una hora
    efficiency_inversor = 0.95 # Eficiencia del inversor, se utiliza par ala conversión DC/AC
    efficiency_charging = 0.90  # Eficiencia en el estado de carga
    C_rate = 5 # Coeficiente para determinar al máximo de energía para la carga y la descarga
    Emax = PB_rate_kW / C_rate # Energía máxima que puede ser descargada o cargada de la batería

    parametros_rest = [
        'min_dg', 'min_bat', 'val_aux', 'val_aux_bateria', 'max_lpsp',
        'PB_rate_kW', 'SOC_min', 'SOC_max', 'SOC_inicial', 'max_ciclos_carga',
        'max_ciclos_descarga', 'self_discharge_coefficient', 'efficiency_charging',
        'efficiency_inversor', 'Emax'
    ]

    dict_restricciones = {
        'min_dg': per_min_dg,
        'min_bat': per_min_bat,
        'val_aux': val_aux_penalizado,
        'val_aux_bateria': val_aux_bateria,
        'max_lpsp': max_lpsp,
        'self_discharge_coefficient': self_discharge_coefficient,
        'PB_rate_kW': PB_rate_kW,
        'SOC_min': SOC_min,
        'SOC_max': SOC_max,
        'SOC_inicial': SOC_inicial,
        'max_ciclos_carga': max_ciclos_carga,
        'max_ciclos_descarga': max_ciclos_descarga,
        'efficiency_inversor': efficiency_inversor,
        'efficiency_charging': efficiency_charging,
        'Emax': Emax
    }

    ############################################################################################
    # Creando diccionario de costos
    # Costos
    cost_pv = 700
    cost_dg = 3000
    cost_bat = 800

    # Variables de decisión
    decision_var = [
        'Pv', 'Dg', 'P_ens', 'Ebat_c', 'Ebat_d', 'n_dc', 'z_dc', 'n_cc', 'z_cc','EMAX_d','EMAX_c', 'Epv_dis'
    ]
    decision_var_SOC = ['SOC_t']
    decision_var_bin = ['B_diesel', 'B_bat_d', 'B_bat_c']

    # diccionario de costos
    dict_cost = {
        'Pv': cost_pv,
        'Dg': cost_dg,
        'Ebat_d': cost_bat,
        'P_ens': 1000000 * cost_dg
    }

    #INICIO DE LA OPTIMIZACION
    ###############################################################################
    model = pyo.ConcreteModel(name = "Dimensionamiento de microrredes")
    #Veces que se correra - Cantidad de periodos a cubrir la carga.
    model.times = pyo.Set(initialize = [i for i in range(len(load))])

    #Inicializo set de variables a considerar reales
    model.variables = pyo.Set(initialize = decision_var)
    model.SOC = pyo.Set(initialize = decision_var_SOC)
    model.bin = pyo.Set(initialize = decision_var_bin)

    #Sets restricciones
    model.restricciones = pyo.Set(initialize = parametros_rest)

    ###################################################################################
    ## Parámetros y variables
    #inicializo parámetros de demanda a cubrir
    model.Demanda = pyo.Param(model.times, initialize = load)
    #Inicializo parámetros de costos
    model.costos = pyo.Param(model.variables, initialize = dict_cost )
    #Parámetros de Capacidad disponible en energía
    model.cap_pv = pyo.Param(model.times, initialize = generacion_pv)
    model.cap_dg = pyo.Param(model.times, initialize = generacion_diesel)
    #model.cap_bat = pyo.Param(model.times, initialize = g_bat) --- Pendiente de modelar.

    #Parámetros de restricciones

    model.restriccion = pyo.Param(model.restricciones, initialize = dict_restricciones)

    #####################################################################################
    ## Variables
    model.binarias = pyo.Var(model.bin, model.times, domain=pyo.Boolean, bounds=(0,1), initialize=0)

    model.var_reales = pyo.Var(model.variables, model.times, within=pyo.NonNegativeReals, initialize=0)

    model.soc_t = pyo.Var(model.SOC, model.times, within=pyo.NonNegativeReals, initialize=0)


    # Función objetivo: minimizar el costo de la energía
    def obj_rule(model):
        """
        Función Objetivo: Minimizar el costo de
        la energía entregada a la carga
        """
        return sum( model.costos['Pv']*model.var_reales['Pv',t] +
                        model.costos['Dg']*model.var_reales['Dg',t] +
                        model.costos['Ebat_d']*model.var_reales['Ebat_d',t] +
                        model.costos['P_ens']*model.var_reales['P_ens',t]            
                        for t in model.times)

    model.generation_cost = pyo.Objective(rule = obj_rule, sense = pyo.minimize)


    #Restricciones

    def demand_rule(model, t):
        """
        Restricción de cumplimiento de la demanda
        """

        return (model.var_reales['Pv', t] + model.var_reales['Dg', t] +
                model.var_reales['Ebat_d', t] +
                model.var_reales['P_ens', t]) == model.Demanda[t]


    model.Dconstraint = pyo.Constraint(model.times, rule=demand_rule)


    def lpsp_rule(model, t):
        """
        Restricción de la máxima probabilidad de 
        pérdida de carga pérmitida (LPSP)
        """
        if model.Demanda[t] <= 0:
            return pyo.Constraint.Skip
        else:
            return sum(model.var_reales['P_ens', t] for t in model.times) / sum(
                model.Demanda[t]
                for t in model.times) <= model.restriccion['max_lpsp']


    model.lpsp_Cap_constraint = pyo.Constraint(model.times, rule=lpsp_rule)


    def capacity_rule_all_(model, i, t):
        """
            Restricción que me garantiza la energía mínima que
            debe despachar de cada generador o variable de la batería
        """

        if 'P_gf' in i:
            return model.var_reales[i, t] >= 0
        elif 'Pv' in i:
            return model.var_reales[i, t] >= 0
        elif 'Dg' in i:
            return model.var_reales[i, t] >= model.binarias[
                'B_diesel', t] * model.cap_dg[t] * model.restriccion['min_dg']
        elif 'Ebat_c' in i:
            return model.var_reales[i, t] >= 0
        elif 'Ebat_d' in i:
            return model.var_reales[i, t] >= 0
        else:
            return pyo.Constraint.Skip


    model.Cap_constraint_rule_all_ = pyo.Constraint(model.variables,
                                                    model.times,
                                                    rule=capacity_rule_all_)

    def aux_rule_diesel(model, i, t):
        """
        Restricción auxiliar de capacidad del diésel y batería
        Sirve para mantener el modelo de tipo líneal
        """
        if 'Dg' in i:
            return model.var_reales[i, t] <= model.restriccion[
                'val_aux'] * model.binarias['B_diesel', t]
        else:
            return pyo.Constraint.Skip


    model.aux_constraint = pyo.Constraint(model.variables,
                                        model.times,
                                        rule=aux_rule_diesel)

    def capacity_max_rule(model, i, t):
        """
            Restricción de la máxima capacidad
            disponible de energía en el 
            sistema X.    
        """

        if 'Pv' in i:
            return model.var_reales[i, t] <= model.cap_pv[t]
        elif 'Dg' in i:
            return model.var_reales[i, t] <= model.cap_dg[t]  # *model.binaria[i,t]
        else:
            return pyo.Constraint.Skip


    model.max_Cap_constraint = pyo.Constraint(model.variables,
                                            model.times,
                                            rule=capacity_max_rule)


    def Energy_max_deliver_bat(model, i, t):
        """
        Control del mínimo estado de carga de la batería
        Control de capacidad física de la batería, es decir, 
        Solo deliberara el mínimo entre el Emax o el Estado de
        carga por cargar disponible o descargar.
        Límita los horizontes.
        """
        if 'Ebat_d' in i:
            return (model.var_reales[i, t] <=
                    model.soc_t['SOC_t', t] - model.restriccion['SOC_min'])

        elif 'Ebat_c' in i:
            return (model.var_reales[i, t] <=
                    model.restriccion['SOC_max'] - model.soc_t['SOC_t', t])

        else:
            return pyo.Constraint.Skip


    model.Energy_max_deliver_bat_ = pyo.Constraint(model.variables,
                                                model.times,
                                                rule=Energy_max_deliver_bat)


    def min_state_of_charge(model, t):
        """
        Control del mínimo estado de carga de la batería
        Control de capacidad física de la batería
        """
        return model.soc_t['SOC_t', t] >= model.restriccion['SOC_min']


    model.min_state_of_charge_t = pyo.Constraint(model.times,
                                                rule=min_state_of_charge)


    #
    def max_state_of_charge(model, t):
        """
        Control del máximo estado de carga de la batería
        Control de capacidad física de la batería
        """
        return model.soc_t['SOC_t', t] <= model.restriccion['SOC_max']


    model.max_state_of_charge_t = pyo.Constraint(model.times,
                                                rule=max_state_of_charge)


    def state_of_charge_equal(model, t):
        """
        Cálculo del estado de carga SOC(t)
        """
        if t == 0:
            return (model.soc_t['SOC_t', t] == model.restriccion['PB_rate_kW'] *
                    (1 - model.restriccion['self_discharge_coefficient'])
                    + model.var_reales['Ebat_c', t] * model.restriccion[
                        'efficiency_charging'] - model.var_reales[
                            'Ebat_d', t] / model.restriccion['efficiency_inversor'])

        else:
            return (model.soc_t['SOC_t', t] == (
                (1 - model.restriccion['self_discharge_coefficient']) *
                model.soc_t['SOC_t', t - 1] + model.var_reales['Ebat_c', t] *
                model.restriccion['efficiency_charging'] -
                model.var_reales['Ebat_d', t] /
                model.restriccion['efficiency_inversor']))


    model.state_of_charge_equal_t = pyo.Constraint(model.times,
                                                rule=state_of_charge_equal)


    def charge_only_pv_to_bat(model, i, t):
        """
        Energía con la que se cargara la batería
        Se tiene en cuenta solo la energía que sobre del panel fotovoltaico
        después de suplir la carga
        """
        if 'Ebat_c' in i:

            return model.var_reales[i, t] <= (model.cap_pv[t] -
                                            model.var_reales['Pv', t])

        else:
            return pyo.Constraint.Skip


    model.charging_only_pv_to_bat = pyo.Constraint(model.variables,
                                                model.times,
                                                rule=charge_only_pv_to_bat)


    #def E_only_pv_dis_to_bat(model, i, t):
    #    """
    #    Energía con la que se cargara la batería
    #    Se tiene en cuenta solo la energía que sobre del panel fotovoltaico
    #    después de suplir la carga
    #    """
    #    if 'Ebat_c' in i:
    #        return model.var_reales['Epv_dis', t] == (model.cap_pv[t] -
    #                                                  model.var_reales['Pv', t])
    #    else:
    #        return pyo.Constraint.Skip
    #
    #
    #model.E_only_pv_dis_to_bat_ = pyo.Constraint(model.variables,
    #                                             model.times,
    #                                             rule=E_only_pv_dis_to_bat)


    def battery_capacity_min_rule_carga(model, i, t):
        """
        Restricciones mínimas asociadas a la batería
        """
        if 'Ebat_c' in i:
            return model.var_reales[
                i, t] <= model.binarias['B_bat_c', t] * model.restriccion['Emax']
        else:
            return pyo.Constraint.Skip


    model.min_Cap_bat_c_constraint = pyo.Constraint(
        model.variables, model.times, rule=battery_capacity_min_rule_carga)


    def aux_rule_bat_carga(model, i, t):
        """
        Restricción auxiliar de capacidad mínima de la batería
        Sirve para mantener el modelo de tipo líneal
        """
        if 'Ebat_c' in i:
            return model.var_reales[i, t] >= model.restriccion[
                'val_aux_bateria'] * model.binarias['B_bat_c', t]
        else:
            return pyo.Constraint.Skip


    model.aux_bat_c_constraint = pyo.Constraint(model.variables,
                                                model.times,
                                                rule=aux_rule_bat_carga)

    def battery_capacity_min_rule_descarga(model, i, t):
        """
        Restricciones mínimas asociadas a la batería
        """
        if 'Ebat_d' in i:
            return model.var_reales[i, t] >= model.binarias[
                'B_bat_d', t] * model.restriccion['val_aux_bateria']
        else:
            return pyo.Constraint.Skip


    model.min_Cap_bat_d_constraint = pyo.Constraint(
        model.variables, model.times, rule=battery_capacity_min_rule_descarga)


    def aux_rule_bat_descarga(model, i, t):
        """
        Restricción auxiliar de capacidad mínima de la batería
        Sirve para mantener el modelo de tipo líneal
        """
        if 'Ebat_d' in i:
            return model.var_reales[
                i, t] <= model.restriccion['Emax'] * model.binarias['B_bat_d', t]
        else:
            return pyo.Constraint.Skip


    model.aux_bat_d_constraint = pyo.Constraint(model.variables,
                                                model.times,
                                                rule=aux_rule_bat_descarga)


    def conteo_ciclos_lineal_descarga(model, i, t):
        """
        Restricción auxiliar de capacidad 
        mínima de la batería sirve para 
        mantener el modelo de tipo líneal
        """
        if 'n_dc' in i:
            return (model.var_reales[i, t] == sum(model.var_reales['z_dc', t]
                                                for t in model.times))
        elif 'z_dc' in i:
            return model.var_reales[i, t] >= 0
        else:
            return pyo.Constraint.Skip


    model.conteo_ciclos_lineal_descarga_1 = pyo.Constraint(
        model.variables, model.times, rule=conteo_ciclos_lineal_descarga)


    def conteo_ciclos_lineal_descarga_dos(model, i, t):
        """
        Restricción auxiliar de capacidad 
        mínima de la batería sirve para 
        mantener el modelo de tipo líneal
        """
        if 'n_dc' in i:
            return (model.var_reales[i, t] <= model.restriccion['val_aux'])
        elif 'z_dc' in i:
            if t != 0:
                return model.var_reales[i, t] >= model.binarias[
                    'B_bat_d', t] - model.binarias['B_bat_d', t - 1]
            else:
                return pyo.Constraint.Skip
        else:
            return pyo.Constraint.Skip


    model.conteo_ciclos_lineal_descarga_2 = pyo.Constraint(
        model.variables, model.times, rule=conteo_ciclos_lineal_descarga_dos)

    def conteo_ciclos_lineal_carga(model, i, t):
        """
        Restricción auxiliar de capacidad 
        mínima de la batería sirve para 
        mantener el modelo de tipo líneal
        """
        if 'n_cc' in i:
            return (model.var_reales[i, t] == sum(model.var_reales['z_cc', t]
                                                for t in model.times))
        elif 'z_cc' in i:
            return model.var_reales[i, t] >= 0
        else:
            return pyo.Constraint.Skip


    model.conteo_ciclos_lineal_carga_1 = pyo.Constraint(
        model.variables, model.times, rule=conteo_ciclos_lineal_carga)


    def conteo_ciclos_lineal_carga_dos(model, i, t):
        """
        Restricción auxiliar de capacidad 
        mínima de la batería sirve para 
        mantener el modelo de tipo líneal
        """
        if 'n_cc' in i:
            return (model.var_reales[i, t] <= model.restriccion['val_aux'])
        elif 'z_cc' in i:
            if t != 0:
                return (model.var_reales[i, t] >= model.binarias['B_bat_c', t] -
                        model.binarias['B_bat_c', t - 1])
            else:
                return pyo.Constraint.Skip
        else:
            return pyo.Constraint.Skip


    model.conteo_ciclos_lineal_carga_2 = pyo.Constraint(
        model.variables, model.times, rule=conteo_ciclos_lineal_carga_dos)

    def max_ciclos_carga_descarga(model, i, t):
        """
        Restricción que controla el número 
        máximo de ciclos de carga y descarga
        para la batería
        """
        if 'n_dc' in i:
            return (model.var_reales[i, t] <=
                    model.restriccion['max_ciclos_descarga'])
        elif 'n_cc' in i:
            return (model.var_reales[i, t] <=
                    model.restriccion['max_ciclos_carga'])
        else:
            return pyo.Constraint.Skip


    model.max_ciclos_carga_descarga_ = pyo.Constraint(
        model.variables, model.times, rule=max_ciclos_carga_descarga)

    return model