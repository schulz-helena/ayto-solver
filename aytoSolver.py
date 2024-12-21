from ortools.sat.python import cp_model

class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables: list[cp_model.IntVar], num_columns: int, women: dict, men: dict, format: str):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0
        self.__num_columns = num_columns
        self.__format = format

    def on_solution_callback(self) -> None:
        self.__solution_count += 1
        print(f"Solution {self.__solution_count}:\n", end=" ")
        if self.__format == "both" or self.__format == "table":
            count = 0
            for v in self.__variables:
                count +=1
                if count == self.__num_columns:
                    print(f"{self.value(v)}\n", end=" ")
                    count = 0
                else: 
                    print(f"{self.value(v)}", end=" ")
            print()
        if self.__format == "both" or self.__format == "names":
            matches = ""
            for v in self.__variables:
                if self.value(v) == 1:
                    pair = str(v).split("+")
                    woman_id = int(pair[0])
                    woman = list(women.keys())[list(women.values()).index(woman_id)]
                    man_id = int(pair[1])
                    man = list(men.keys())[list(men.values()).index(man_id)]
                    match = f"{woman} & {man}"
                    if matches:
                        matches = f"{matches}, {match}"
                    else:
                        matches = f"{match}"
            print(matches)
            print()
        
    @property
    def solution_count(self) -> int:
        return self.__solution_count


def txt_reader(filepath: str):
    women = dict()
    men = dict()
    matchingNights = []
    matchBoxes = []
    mn = False
    mb = False
    with open(filepath) as f:
        lines = f.readlines()
    f.close()
    for l, line in enumerate(lines):
        line = line.strip()
        line = line.split(", ")
        if l == 0:
            for e, elem in enumerate(line):
                women[elem] = e
        if l == 1:
            for e, elem in enumerate(line):
                men[elem] = e
        if l == 2:
            part_of_doublematch = line[0]
            if part_of_doublematch == "":
                part_of_doublematch = None
            elif part_of_doublematch in men:
                part_of_doublematch = men[part_of_doublematch]
            elif part_of_doublematch in women:
                part_of_doublematch = women[part_of_doublematch]
        if line[0] == "MB:":
            mn = False
            mb = True
        elif mb:
            box = []
            if line[0] != "-": # if match box was not sold
                box.append(int(line.pop(0)))
                names = line[0]
                names = names.split("+")
                names[0] = women[names[0]]
                names[1] = men[names[1]]
                box.append(names)
            matchBoxes.append(box)
        if line[0] == "MN:":
            mn = True
        elif mn:
            night = []
            night.append(int(line.pop(0)))
            for e, elem in enumerate(line):
                elem = elem.split("+")
                elem[0] = women[elem[0]]
                elem[1] = men[elem[1]]
                night.append(elem)
            matchingNights.append(night)
    return women, men, matchingNights, matchBoxes, part_of_doublematch


def csp_solver(women: dict, men: dict, matchingNights: list, matchBoxes: list, part_of_doublematch: int, until_night: int, format: str):
    # Create the mip solver with the SCIP backend.
    model = cp_model.CpModel()
    
    num_women = len(women)
    num_men = len(men)
    # Variables
    x = {}
    for i in range(num_women): # Frauen sind die Reihen
        for j in range(num_men): # Männer sind die Spalten
            x[i,j] = model.new_int_var(0, 1, f"{str(i)}+{str(j)}") # Paar kann Wert 0 ("No Match") oder 1 ("Perfect Match") haben
    

    # Constraints
    # Ein Mann ist übrig, bzw. eine Frau hat zwei Matches
    if num_men > num_women:
        for i in range(num_women): # Row constraint
            if part_of_doublematch: # Wenn wir wissen, welcher Mann Teil des Doppelmatches ist
                model.Add(sum([x[i,j] for j in range(num_men)]) - x[i, part_of_doublematch] == 1)
            else: # Ansonsten könnte es jeder Mann sein
                model.Add(sum([x[i,j] for j in range(num_men)]) <= 2)
                model.Add(sum([x[i,j] for j in range(num_men)]) > 0)
        for j in range(num_men): # Column constraint
            model.Add(sum([x[i,j] for i in range(num_women)]) == 1)
        model.Add(sum([x[i,j] for i in range(num_women) for j in range(num_men)]) == num_men) # Insgesamt gibt es 11 Matches
    # Eine Frau ist übrig, bzw. ein Mann hat zwei Matches
    else: 
        for i in range(num_women): # Row constraint
            model.Add(sum([x[i,j] for j in range(num_men)]) == 1)
        for j in range(num_men): # Column constraint
            if part_of_doublematch: # Wenn wir wissen, welche Frau Teil des Doppelmatches ist
                model.Add(sum([x[i,j] for i in range(num_women)]) - x[part_of_doublematch, j] == 1)
            else: # Ansonsten könnte es jede Frau sein
                model.Add(sum([x[i,j] for i in range(num_women)]) <= 2)
                model.Add(sum([x[i,j] for i in range(num_women)]) > 0)
        model.Add(sum([x[i,j] for i in range(num_women) for j in range(num_men)]) == num_women) # Insgesamt gibt es 11 Matches


    # Only use information from matching nights and match boxes until (not including) a certain matching night
    if until_night:
        matchingNights = matchingNights[:until_night] # ab until_night abcutten
        matchBoxes = matchBoxes[:until_night] # ab until_night abcutten
    # else just use all available information

    # Matching-Nights
    for night in matchingNights:
        lights = night.pop(0)
        model.Add(sum([x[i,j] for [i,j] in night]) == lights)

    # Match-Boxes
    for box in matchBoxes:
        if box: # if this match box was not sold
            if_match = box.pop(0)
            model.Add(x[box[0][0], box[0][1]] == if_match)
    #x[0,0].Proto().domain[:] = []
    #x[0,0].Proto().domain.extend(cp_model.Domain(1, 1).FlattenedIntervals())


    # Solve
    solver = cp_model.CpSolver()
    solution_printer = VarArraySolutionPrinter([x[i,j] for i in range(num_women) for j in range(num_men)], num_men, women, men, format)
    #solver.parameters.enumerate_all_solutions = False
    #solver.parameters.max_time_in_seconds = 2
    solver.SearchForAllSolutions(model, solution_printer)
    #print(f"Number of solutions found: {solution_printer.solution_count}")

if __name__ == "__main__":
    women, men, matchingNights, matchBoxes, part_of_doublematch = txt_reader("vip2024.txt")
    csp_solver(women, men, matchingNights, matchBoxes, part_of_doublematch, 7, "names")

# 2-dimensionale Variablen (alle Männer-Frauen Kombinationen):
# - Jede Kombination aus Mann und Frau ist eine Variable
# - Domänen: binär, 1 für Match, 0 für kein Match
# - Reihen- und Spaltenconstraints: Summe = 1 (Frau:Mann ist eine 1:1-Beziehung)
# - Match-Boxes legen den Wert einer Variable fest (1 = "Perfect Match", 0 = "No Match")
# - Matching-Nights legen die Summe aller 10 Variablen, die die gewählten Paare sind, als die Anzahl der Lichter fest
# -----------------------------------------------------
# Frauen als Variablen:
# - Frauen sind die Variablen, jeder Mann ist ein Wert in der Domain jeder Variable
# - Match-Boxes legen entweder den Wert einer Variable fest ("Perfect Match") oder 
#   nehmen einen Wert aus der Domain einer Variable heraus ("No Match")
# - Jede Variable hat genau einen Wert
# - Alle Variablen haben unterschiedliche Werte, außer eine Variable (in der aktuellen Staffel Dana), 
#   die den gleichen Wert hat wie eine der anderen Variablen -> außer diese eine Variable ein all-different Constraint
# - Aber wie modelliert man die Anzahl der Lichter in den Matching-Nights?
# -----------------------------------------------------
# Männer als Variablen:
# - Männer sind die Variablen, jede Frau ist ein Wert in der Domain jeder Variable
# - Match-Boxes legen entweder den Wert einer Variable fest ("Perfect Match") oder 
#   nehmen einen Wert aus der Domain einer Variable heraus ("No Match")
# - Jede Variable hat genau einen Wert
# - Alle Variablen haben unterschiedliche Werte -> all-different Constraint
# - Dana wird quasi ignoriert, sie ist kein Domain-Wert, steht sie in einer Matching-Night 
#   alleine da passiert nichts, sitzt sie mit jemandem, wird die allein stehende Frau als Wert des Mannes eingetragen
# - Matching-Nights sind eine Belegung jeder Variable mit einem Wert, wobei die Anzahl der Lichter angibt, wie viele
#   der Belegungen korrekt sind (geht das?)
# -----------------------------------------------------
# Wären es immer 10 Frauen und 10 Männer, wäre das Ganze ein permutation problem (n Variablen, n Werte und jede Variable braucht einen individuellen Wert)
# Es gibt 2 mögliche Viewpoints: Frauen als Variablen und Männer als Variablen (einer ist der dual viewpoint des anderen Viewpoints, beide Modelle sind mutually redundant)
# Ich habe mich hier für ein Boolean Model entschieden (hat eine Boolean variable x_ij für jede mögliche Variable-Wert Kombination)
# Wenn es mehr Werte als Variablen gibt: injection problem