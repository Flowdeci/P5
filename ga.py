import copy
import heapq
import metrics
import multiprocessing.pool as mpool
import os
import random
import shutil
import time
import math

width = 200
height = 16

options = [
    "-",  # an empty space
    "X",  # a solid wall
    "?",  # a question mark block with a coin
    "M",  # a question mark block with a mushroom
    "B",  # a breakable block
    "o",  # a coin
    "|",  # a pipe segment
    "T",  # a pipe top
    "E",  # an enemy
    # "f",  # a flag, do not generate
    # "v",  # a flagpole, do not generate
    # "m"  # mario's start position, do not generate
]

# The level as a grid of tiles


class Individual_Grid(object):
    __slots__ = ["genome", "_fitness"]

    def __init__(self, genome):
        self.genome = copy.deepcopy(genome)
        self._fitness = None

    # Update this individual's estimate of its fitness.
    # This can be expensive so we do it once and then cache the result.
    def calculate_fitness(self):
        measurements = metrics.metrics(self.to_level())
        # Print out the possible measurements or look at the implementation of metrics.py for other keys:
        # print(measurements.keys())
        # Default fitness function: Just some arbitrary combination of a few criteria.  Is it good?  Who knows?
        # STUDENT Modify this, and possibly add more metrics.  You can replace this with whatever code you like.
        coefficients = dict(
            # Metrics with positive weights are desirable
            # While metrics with negative weights are undesriable
            meaningfulJumpVariance=0.5,
            negativeSpace=0.6,
            pathPercentage=0.5,
            emptyPercentage=0.6,
            linearity=-0.5,  # Since its negative the less linear a level is the better
            solvability=3.0,  # wieght is extremly high because solvable levels are essentail
        )

        #Penealties for overcrodwing
        overcrowding_penalty = 0
        tile_counts = {
            "pipe": sum(row.count("T") + row.count("|") for row in self.genome),
            "blocks": sum(row.count("?") + row.count("B") for row in self.genome),
            "coins": sum(row.count("o") for row in self.genome),
            "enemies": sum(row.count("E") for row in self.genome),
        }

        # Add penalties for overcrowding
        if tile_counts["pipe"] > 15:
            overcrowding_penalty -= 1
        #if tile_counts["blocks"] > 100:
            #overcrowding_penalty -= 2
        if tile_counts["coins"] >40:
            overcrowding_penalty -= 0.5
        if tile_counts["enemies"] > 15:
            overcrowding_penalty -= 1

        # Penalize lack of ground support for pipes
        floating_pipes_penalty = 0
        ground_level = height - 1
        for x in range(1, width - 1):
            if self.genome[ground_level][x] not in ["X", "T", "|"] and "T" in [row[x] for row in self.genome]:
                floating_pipes_penalty -= 1

        self._fitness = (
            sum(map(lambda m: coefficients[m] * measurements[m], coefficients))
            +floating_pipes_penalty
            +overcrowding_penalty
        )
        return self

    # Return the cached fitness value or calculate it as needed.
    def fitness(self):
        if self._fitness is None:
            self.calculate_fitness()
        return self._fitness

   
    # Mutate a genome into a new genome.  Note that this is a _genome_, not an individual!
    def mutate(self, genome):
        # STUDENT implement a mutation operator, also consider not mutating this individual
        # STUDENT also consider weighting the different tile types so it's not uniformly random
        # STUDENT consider putting more constraints on this to prevent pipes in the air, etc

        #randomly decided wehter to mutate the level at all
        if random.random() > 0.5:
            return genome
        left = 1  # first column
        right = width - 1  # last column
        ground_level=height-1;
        player_start_x = 0

        #ADd pipes
        for x in range(left, right):
            if genome[ground_level][x]=="X" and random.random()<0.02:

                pipe_height=random.randint(1,4);
                can_place_pipe=all(
                    genome[ground_level - i][x] == "-" for i in range(1, pipe_height + 1)
                )#Ensure that a pipe can be placced on ground with enough space going up

                if can_place_pipe:
                    for i in range(1,pipe_height+1):
                        genome[ground_level-i][x]="|"
                    genome[ground_level-pipe_height][x]="T"
        
        #Add floating platforms
        for y in range(5, ground_level-1):
            # Add in the middle part of the level
            for x in range(left, right-2, 4):
                # Check every 4 tiles to reduce clustering
                if random.random()<0.04:
                    platform_wdith=random.randint(2,5);

                    #check if all the platofrm is all air
                    can_place_platform = all(
                        genome[y][x + i] == "-" and genome[y + 2][x + i] == "-" and genome[y - 2][x + i] == "-"and genome[y + 1][x + i] == "-" and genome[y - 1][x + i] == "-"
                        for i in range(platform_wdith)
                    )
                    if can_place_platform:
                        for i in range(platform_wdith):
                            genome[y][x+i]=random.choices(["X","?","o","M"],weights=[60, 15,10,15], k=1)[0];

       
        enemy_cap = 20
        enemy_count = sum(row.count("E") for row in genome)  
         # Place enemies on ground
        for x in range(left, right):
            if genome[ground_level][x] == "X" and genome[ground_level - 1][x] == "-":
                if random.random() < 0.01: 
                    #make sure no enmeis with 5 blocks of player
                    if abs(x - player_start_x) > 5:
                        genome[ground_level - 1][x] = "E"
                        enemy_count += 1
                        if enemy_count >= enemy_cap/2:
                            break
        # gerneate a list of all possible coordinates
        coordinates = [(x, y) for y in range(1, ground_level) for x in range(left, right)]
        random.shuffle(coordinates)  # randomize the order of coordinates
        #Spawn enmies in the air
        for x, y in coordinates:
            if genome[y][x] in ["X", "?", "B", "M"] and genome[y - 1][x] == "-":
                if random.random() < 0.01 and enemy_count < enemy_cap: 
                    genome[y - 1][x] = "E"
                    enemy_count += 1
                    if enemy_count >= enemy_cap:
                        break

        #Place coins
        for y in range(5, ground_level-1):
            for x in range(left, right):
                if genome[y][x]=='-' and genome[y+1][x] in ["X","?"]:
                    if random.random()<0.02:
                        genome[y][x]="o"

        random_block_count = random.randint(5, 20)  # Add a random number of blocks
        for _ in range(random_block_count):
            x = random.randint(left, right - 1)
            y = random.randint(1, ground_level - 1)  # Avoid placing on the top or ground levels

            if genome[y][x] == "-":  # Only place blocks in empty spaces
                genome[y][x] = random.choices(["X", "?", "B", "M","E","o"], weights=[50, 15, 15, 10,5,5], k=1)[0]

        return genome


    def generate_children(self, other):
        new_genome = copy.deepcopy(self.genome)

        #Make children by replacing chunks of the parents
        chunk_size = 10
        num_chunks = width // chunk_size

        for chunk in range(num_chunks):
            if random.random() < 0.5:  # 50% chance to take a chunk from the other parent
                start_col = chunk * chunk_size
                end_col = start_col + chunk_size

                # replace the chunk of columns with the other parents chunk
                for y in range(height):
                    for x in range(start_col, end_col):
                        new_genome[y][x] = other.genome[y][x]

        # apply mutation
        child = Individual_Grid(new_genome)
        child.mutate(child.genome)
        return (child,)

    def to_level(self):
        return self.genome

    # These both start with every floor tile filled with Xs
    # STUDENT Feel free to change these
    @classmethod
    def empty_individual(cls):
        g = [["-" for col in range(width)] for row in range(height)]
        g[15][:] = ["X"] * width
        g[14][0] = "m"
        g[7][-2] = "v"
        for col in range(8, 14):
            g[col][-2] = "f"
        for col in range(14, 16):
            g[col][-2] = "X"
        return cls(g)

    @classmethod
    def random_individual(cls):
        # STUDENT consider putting more constraints on this to prevent pipes in the air, etc
        # STUDENT also consider weighting the different tile types so it's not uniformly random
        g = [random.choices(options, k=width) for row in range(height)]
        g[15][:] = ["X"] * width
        g[14][0] = "m"
        g[7][-1] = "v"
        g[8:14][-1] = ["f"] * 6
        g[14:16][-1] = ["X", "X"]
        return cls(g)


def offset_by_upto(val, variance, min=None, max=None):
    val += random.normalvariate(0, variance**0.5)
    if min is not None and val < min:
        val = min
    if max is not None and val > max:
        val = max
    return int(val)


def clip(lo, val, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


# Inspired by https://www.researchgate.net/profile/Philippe_Pasquier/publication/220867545_Towards_a_Generic_Framework_for_Automated_Video_Game_Level_Creation/links/0912f510ac2bed57d1000000.pdf


class Individual_DE(object):
    # Calculating the level isn't cheap either so we cache it too.
    __slots__ = ["genome", "_fitness", "_level"]

    # Genome is a heapq of design elements sorted by X, then type, then other parameters
    def __init__(self, genome):
        self.genome = list(genome)
        heapq.heapify(self.genome)
        self._fitness = None
        self._level = None

    # Calculate and cache fitness
    def calculate_fitness(self):
        measurements = metrics.metrics(self.to_level())
        # Default fitness function: Just some arbitrary combination of a few criteria.  Is it good?  Who knows?
        # STUDENT Add more metrics?
        # STUDENT Improve this with any code you like
        coefficients = dict(
            meaningfulJumpVariance=0.5,
            negativeSpace=0.6,
            pathPercentage=0.5,
            emptyPercentage=0.6,
            linearity=-0.5,
            solvability=2.0,
        )
        penalties = 0
        # STUDENT For example, too many stairs are unaesthetic.  Let's penalize that
        if len(list(filter(lambda de: de[1] == "6_stairs", self.genome))) > 5:
            penalties -= 2
        # STUDENT If you go for the FI-2POP extra credit, you can put constraint calculation in here too and cache it in a new entry in __slots__.
        self._fitness = (
            sum(map(lambda m: coefficients[m] * measurements[m], coefficients))
            + penalties
        )
        return self

    def fitness(self):
        if self._fitness is None:
            self.calculate_fitness()
        return self._fitness

    def mutate(self, new_genome):
        # STUDENT How does this work?  Explain it in your writeup.
        # STUDENT consider putting more constraints on this, to prevent generating weird things
        if random.random() < 0.1 and len(new_genome) > 0:
            to_change = random.randint(0, len(new_genome) - 1)
            de = new_genome[to_change]
            new_de = de
            x = de[0]
            de_type = de[1]
            choice = random.random()
            if de_type == "4_block":
                y = de[2]
                breakable = de[3]
                if choice < 0.33:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.66:
                    y = offset_by_upto(y, height / 2, min=0, max=height - 1)
                else:
                    breakable = not de[3]
                new_de = (x, de_type, y, breakable)
            elif de_type == "5_qblock":
                y = de[2]
                has_powerup = de[3]  # boolean
                if choice < 0.33:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.66:
                    y = offset_by_upto(y, height / 2, min=0, max=height - 1)
                else:
                    has_powerup = not de[3]
                new_de = (x, de_type, y, has_powerup)
            elif de_type == "3_coin":
                y = de[2]
                if choice < 0.5:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                else:
                    y = offset_by_upto(y, height / 2, min=0, max=height - 1)
                new_de = (x, de_type, y)
            elif de_type == "7_pipe":
                h = de[2]
                if choice < 0.5:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                else:
                    h = offset_by_upto(h, 2, min=2, max=height - 4)
                new_de = (x, de_type, h)
            elif de_type == "0_hole":
                w = de[2]
                if choice < 0.5:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                else:
                    w = offset_by_upto(w, 4, min=1, max=width - 2)
                new_de = (x, de_type, w)
            elif de_type == "6_stairs":
                h = de[2]
                dx = de[3]  # -1 or 1
                if choice < 0.33:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.66:
                    h = offset_by_upto(h, 8, min=1, max=height - 4)
                else:
                    dx = -dx
                new_de = (x, de_type, h, dx)
            elif de_type == "1_platform":
                w = de[2]
                y = de[3]
                madeof = de[4]  # from "?", "X", "B"
                if choice < 0.25:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.5:
                    w = offset_by_upto(w, 8, min=1, max=width - 2)
                elif choice < 0.75:
                    y = offset_by_upto(y, height, min=0, max=height - 1)
                else:
                    madeof = random.choice(["?", "X", "B"])
                new_de = (x, de_type, w, y, madeof)
            elif de_type == "2_enemy":
                pass
            new_genome.pop(to_change)
            heapq.heappush(new_genome, new_de)
        return new_genome

    def generate_children(self, other):
        # STUDENT How does this work?  Explain it in your writeup.
        pa = random.randint(0, len(self.genome) - 1)
        pb = random.randint(0, len(other.genome) - 1)
        a_part = self.genome[:pa] if len(self.genome) > 0 else []
        b_part = other.genome[pb:] if len(other.genome) > 0 else []
        ga = a_part + b_part
        b_part = other.genome[:pb] if len(other.genome) > 0 else []
        a_part = self.genome[pa:] if len(self.genome) > 0 else []
        gb = b_part + a_part
        # do mutation
        return Individual_DE(self.mutate(ga)), Individual_DE(self.mutate(gb))

    # Apply the DEs to a base level.
    def to_level(self):
        if self._level is None:
            base = Individual_Grid.empty_individual().to_level()
            for de in sorted(self.genome, key=lambda de: (de[1], de[0], de)):
                # de: x, type, ...
                x = de[0]
                de_type = de[1]
                if de_type == "4_block":
                    y = de[2]
                    breakable = de[3]
                    base[y][x] = "B" if breakable else "X"
                elif de_type == "5_qblock":
                    y = de[2]
                    has_powerup = de[3]  # boolean
                    base[y][x] = "M" if has_powerup else "?"
                elif de_type == "3_coin":
                    y = de[2]
                    base[y][x] = "o"
                elif de_type == "7_pipe":
                    h = de[2]
                    base[height - h - 1][x] = "T"
                    for y in range(height - h, height):
                        base[y][x] = "|"
                elif de_type == "0_hole":
                    w = de[2]
                    for x2 in range(w):
                        base[height - 1][clip(1, x + x2, width - 2)] = "-"
                elif de_type == "6_stairs":
                    h = de[2]
                    dx = de[3]  # -1 or 1
                    for x2 in range(1, h + 1):
                        for y in range(x2 if dx == 1 else h - x2):
                            base[clip(0, height - y - 1, height - 1)][
                                clip(1, x + x2, width - 2)
                            ] = "X"
                elif de_type == "1_platform":
                    w = de[2]
                    h = de[3]
                    madeof = de[4]  # from "?", "X", "B"
                    for x2 in range(w):
                        base[clip(0, height - h - 1, height - 1)][
                            clip(1, x + x2, width - 2)
                        ] = madeof
                elif de_type == "2_enemy":
                    base[height - 2][x] = "E"
            self._level = base
        return self._level

    @classmethod
    def empty_individual(_cls):
        # STUDENT Maybe enhance this
        g = []
        return Individual_DE(g)

    @classmethod
    def random_individual(_cls):
        # STUDENT Maybe enhance this
        elt_count = random.randint(8, 128)
        g = [
            random.choice(
                [
                    (random.randint(1, width - 2), "0_hole", random.randint(1, 8)),
                    (
                        random.randint(1, width - 2),
                        "1_platform",
                        random.randint(1, 8),
                        random.randint(0, height - 1),
                        random.choice(["?", "X", "B"]),
                    ),
                    (random.randint(1, width - 2), "2_enemy"),
                    (
                        random.randint(1, width - 2),
                        "3_coin",
                        random.randint(0, height - 1),
                    ),
                    (
                        random.randint(1, width - 2),
                        "4_block",
                        random.randint(0, height - 1),
                        random.choice([True, False]),
                    ),
                    (
                        random.randint(1, width - 2),
                        "5_qblock",
                        random.randint(0, height - 1),
                        random.choice([True, False]),
                    ),
                    (
                        random.randint(1, width - 2),
                        "6_stairs",
                        random.randint(1, height - 4),
                        random.choice([-1, 1]),
                    ),
                    (
                        random.randint(1, width - 2),
                        "7_pipe",
                        random.randint(2, height - 4),
                    ),
                ]
            )
            for i in range(elt_count)
        ]
        return Individual_DE(g)


Individual = Individual_Grid


def generate_successors(population):
    # STUDENT Design and implement this
    # Hint: Call generate_children() on some individuals and fill up results.
    
    #choose parents
    def select_parent(population):
        #roulette whelel selection
        total_fitness=sum(ind.fitness() for ind in population)
        pick=random.uniform(0,total_fitness)
        current=0
        for ind in population:
            #accumlate fitness and stop once its greater than needed
            current+=ind.fitness()
            if current>pick:
                return ind
        #Fallback if none are selected
        return random.choice(population)
        
    # Generate offspring
    next_population=[]
    while(len(next_population)<len(population)):
        parent1=select_parent(population);
        parent2=select_parent(population);

        #Crossover
        child=parent1.generate_children(parent2)[0]

        child.mutate(child.genome)

        next_population.append(child)

    return next_population


def ga():
    # STUDENT Feel free to play with this parameter
    pop_limit = 480
    # Code to parallelize some computations
    batches = os.cpu_count()
    if pop_limit % batches != 0:
        print(
            "It's ideal if pop_limit divides evenly into " + str(batches) + " batches."
        )
    batch_size = int(math.ceil(pop_limit / batches))
    with mpool.Pool(processes=os.cpu_count()) as pool:
        init_time = time.time()
        # STUDENT (Optional) change population initialization
        population = [
            (
                Individual.empty_individual()
                if random.random() < 0.9
                else Individual.empty_individual()
            )
            for _g in range(pop_limit)
        ]
        # But leave this line alone; we have to reassign to population because we get a new population that has more cached stuff in it.
        population = pool.map(Individual.calculate_fitness, population, batch_size)
        init_done = time.time()
        print(
            "Created and calculated initial population statistics in:",
            init_done - init_time,
            "seconds",
        )
        generation = 0
        start = time.time()
        now = start
        improvement_threshold = 0.01
        max_generations_without_improvement = 10
        no_improvement_generations = 0
        best = max(population, key=Individual.fitness)
        current_best_fitness = best.fitness()
        best_fitness=current_best_fitness
        print("Use ctrl-c to terminate this loop manually.")
        try:
            while True:
                now = time.time()
                # Print out statistics
                if generation > 0:
                    best = max(population, key=Individual.fitness)
                    current_best_fitness = best.fitness()
                    print("Generation:", str(generation))
                    print("Max fitness:", str(best.fitness()))
                    print("Average generation time:", (now - start) / generation)
                    print("Net time:", now - start)
                    with open("levels/last.txt", "w") as f:
                        for row in best.to_level():
                            f.write("".join(row) + "\n")
                generation += 1
                # STUDENT Determine stopping condition
                if current_best_fitness - best_fitness < improvement_threshold:
                    no_improvement_generations += 1
                else:
                    no_improvement_generations = 0
                    best_fitness = current_best_fitness

                # Stop if no improvement for too many generations
                if no_improvement_generations >= max_generations_without_improvement:
                    print(
                        f"stopping   early after {generation} generations due to lack of improvement."
                    )
                    break
                # STUDENT Also consider using FI-2POP as in the Sorenson & Pasquier paper
                gentime = time.time()
                next_population = generate_successors(population)
                gendone = time.time()
                print("Generated successors in:", gendone - gentime, "seconds")
                # Calculate fitness in batches in parallel
                next_population = pool.map(
                    Individual.calculate_fitness, next_population, batch_size
                )
                popdone = time.time()
                print("Calculated fitnesses in:", popdone - gendone, "seconds")
                population = next_population
        except KeyboardInterrupt:
            pass
    return population


def main():
    # Parameters
    num_generations = 100  # Maximum number of generations to evolve
    num_levels_to_save = 5  # Save top N levels for analysis

    print("Initializing Genetic Algorithm...")
    final_population = ga()  # Run the genetic algorithm

    # Sort the final population by fitness, descending
    sorted_population = sorted(final_population, key=Individual.fitness, reverse=True)

    # Print statistics about the final population
    print("\nFinal Population Statistics:")
    print(f"Best Fitness: {sorted_population[0].fitness():.4f}")
    print(f"Average Fitness: {sum(ind.fitness() for ind in sorted_population) / len(sorted_population):.4f}")
    print(f"Worst Fitness: {sorted_population[-1].fitness():.4f}")

    # Save the top levels to files
    now = time.strftime("%m_%d_%H_%M_%S")
    output_dir = "levels"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i in range(min(num_levels_to_save, len(sorted_population))):
        file_path = f"{output_dir}/{now}_level_{i + 1}.txt"
        with open(file_path, "w") as f:
            for row in sorted_population[i].to_level():
                f.write("".join(row) + "\n")
        print(f"Saved level {i + 1} to {file_path}")

    print("\nGenetic Algorithm completed.")

if __name__ == "__main__":
    main()