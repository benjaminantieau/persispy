"""
Takes a variety of type string and, after solving intersections with phcpy,
returns a persispy point cloud. We must reject equations with with variables t, 
e, E, i, I because their meanings are reserved.
"""

import numpy as np

from phcpy.solver import total_degree_start_system, total_degree
from phcpy.trackers import track
from phcpy.solutions import strsol2dict # points

from persispy.point_cloud import PointCloud
from persispy.hash_point import HashPoint

from string import ascii_letters, digits



# TODO: Implement poisson sampling
class phc(object):

    # functions available to the user
    def __dir__(self):
        return ["eqn", "varList", "degree", "points", "find_more_points()"]

    def __init__(self, eqn, num_points = 1, bounds = 1, return_complex = False, DEBUG = False):
        self._DEBUG = DEBUG

        self._bounds = bounds
        self._complex_epsilon = 0.1
        self._failure = num_points

        self.eqn = eqn

        self.varList, self.coeffList = self._parse(eqn)
        self.total_coeff = sum(self.coeffList)
#         self._bounds = self.total_coeff

        self.degree = self._degree()
        self.points = []


        self._startSystem, self._startSol = self._start_system()
        
        partition = 200
            
        i = 0
        while(i < num_points/partition):
            i = i + 1
            self.find_more_points(partition, return_complex)
        self.find_more_points(num_points%partition, return_complex)


        self.__call__()


    # Parsing target variety into a string usable by phcpy and to generate
    # intersects
    def _parse(self, eqn):

        if self._DEBUG:
            print "====="
            print "input eqn: ", eqn+";"
            print "====="

        terms = eqn
        # Extracting terms from the target
        for x in ["+","-","*","**","^"]: terms = terms.replace(x, " ")
        terms = terms.strip(" ")
        varList = []
        for x in terms:
            if x in ["e", "E", "i", "I", "t"]:
                raise RuntimeError("\""+x+"\" is reserved. Please use a " \
                    "different variable.")
            if not x.isdigit() and x.isalnum() and x not in varList:
                varList.append(x)
        varList.sort()
        if self._DEBUG: print "list of variables: ", varList

        coeffs = eqn
        coeffs = coeffs.replace("-", "+")
        coeffs = coeffs.replace(" ", "")
        coeffs = coeffs.split("+")
        coeffList = []

        for x in coeffs:
            has_term = False
            for y in x:
                if y in ascii_letters:
                    has_term = True
                    break
            if has_term:
                cut = 0
                for y in x:
                    if y in digits \
                            or y == ".":
                        cut = cut + 1
                    else:
                        if cut == 0:
                            coeffList.append(1)
                        else:
                            coeffList.append(float(x[0:cut]))
                        break

        return varList, coeffList

    def _degree(self):
        return total_degree(self._system())

    #  The for loop ensures the system is "square", where number of
    #  variables = number of equations. The resulting points are regular,
    #  bounded by the variety.
    def _system(self):
        phcEqn = self.eqn+";"
        p = [phcEqn]
        for x in range(len(self.varList)-1): p.append(self._intersect())
        return p

    #  This first block sets up the start system so the solver
    #  doesn't need to make a new one for each intersection
    def _start_system(self):
        # It is possible to use a dictionary instead of a list
        # but is possibly unnecessary to store the intersect
        if self._DEBUG: self.attempt = 0

        p = self._system()
        startSystem, startSol = total_degree_start_system(p)
        if self._DEBUG:
            print "system of equations"
            print "--"
            for x in p: print x
            print "--"
            print "start solutions: ", len(startSol)
            for x in startSystem: print x
            for x in startSol: print x
            self.attempt = self.attempt + 1
            print "self.attempt #"+str(self.attempt)
        return startSystem, startSol


    #  Uses the already made start system. Otherwise, identical to 
    #  the block above
    def find_more_points(self, num_points, return_complex = False):
        
        # phcpy solver
        points = []
        failure = 0
        while(len(points) < num_points):
            p = self._system()
            phcSol = track(p, self._startSystem, self._startSol, gamma=complex(0.824,0.5664))
            if self._DEBUG:
                print "system of equations"
                print "--"
                for x in p: print x
                print "--"
                print "number of solutions: ", len(phcSol)
                self.attempt = self.attempt + 1
                print "attempt #"+str(self.attempt)

            #  Parsing the output of phcSol
            for i in phcSol:
                if self._DEBUG: print "phc solution: \n", i 
                d = strsol2dict(i)
                
                point = [d[x] for x in self.varList]
                if return_complex:
                    points.append(tuple(point))
                else:
                    closeness = True 
                    for component in point: 
                    # choses the points we want
                        if self._is_close(component.imag) \
                                and self._in_bounds(component.real):
                            # sometimes phcpy gives more points than we ask,
                            # thus the additional check
                            if component == point[-1] \
                                    and closeness == True \
                                    and len(points) < num_points: 
                                points.append(tuple([component.real for component in point]))
                                if self._DEBUG: print "appended point:",[component.real for component in point]
                                failure = 0
                        else:
                            closeness = False
                            failure = failure + 1
            if self._failure <= failure:
                raise RuntimeError("equation has too many complex solutions in a row")

        if self._DEBUG: print "points: ", points

        self.points = points + self.points

    # "intersect()" forms intersects from extracted the terms. Returns a plane 
    # with random coefficients to intersect the variety. The intersects must be
    # of the same dim as the variety to prevent a overdetermined or 
    # underdetermined systems.
    def _intersect(self):
        bounds = self._bounds
        rand_list = np.random.uniform(-bounds, bounds, size=len(self.varList))
#         rand_list = np.random.normal(0, bounds, size=len(self.varList))
        i = 0
        intersect = [] 
        for x in rand_list:
            intersect.append(str(x)+" * "+self.varList[i])
            if i < len(rand_list)-1: intersect.append(" + ")
            i = i + 1
        intersect.append(";")
        intersect = "".join(intersect)
        return intersect

    # for dealing with the fact that PHC always returns complex solutions
    # To be used to detect solutions with complex parts close to given epsilon
    # Adjust epsilon to your liking.
    # Note: phcpack almost always gives an imaginary part, as small as 10^-48,
    # so epsilon != 0
    def _is_close(self, a, b = 0):
        epsilon = self._complex_epsilon
        if self._DEBUG \
                and abs(a - b) <= epsilon: print "Selected component is close" 
        return abs(a - b) <= epsilon

    def _in_bounds(self, a):
        bounds = self._bounds
        min = -bounds
        max = bounds
        if bounds != 0 and \
                min <= a and \
                a <= max:
            if self._DEBUG: print "Selected component is in bounds"
            return True
        else:
            return False

    def __call__(self):
        cloudPoints = []
        i = 0
        for coord in self.points:
            cloudPoints.append(
                HashPoint(
                    np.array(
                        coord, 
                        dtype=complex
                    ),
                    index = i
                )
            )
            i = i + 1
        self.pointCloud = PointCloud(cloudPoints) 
        return self.pointCloud

# for printing the points
# eg.
# $ print phc
    def __str__(self):
        self.__call__()
        return self.pointCloud.__str__()

    def __repr__(self):
        return self.points.__repr__()

    def __len__(self):
        return len(self.points)

# returns a point
    def __getitem__(self, key):
        return self.points[key]

# allows PointCloud methods to be called on the instance
    def __getattr__(self, name):
        try:
            return getattr(self.pointCloud, name)
        except AttributeError:
            raise




def main():
    global pc
    user = raw_input("torus or sphere? ")
    if user == "torus":
        selection = "16*x^2 + 16*y^2 - (x^2 + y^2 + z^2 + 3)^2"
    elif user == "sphere":
        selection = "x^2 + y^2 + z^2 - 1"
    else:
        print "invalid input"
        return

    pc = phc(eqn = selection, num_points = 5000, bounds = 30)

    global ng
#     ng = pc.neighborhood_graph(0.2)
    print pc
    pc.find_more_points(10)
    print pc
    print pc[0]
    print pc.points[0]
    print pc.degree
    print pc.total_coeff
    print pc.plot3d()

    saveUser = raw_input("save file? ")
    if saveUser == "yes":
        fileUser = raw_input("file name? ")
        f = open(fileUser, "wa")
        f.write(str(pc.points))
        f.close()
    else:
        print "exiting"




if __name__ == "__main__": main()
