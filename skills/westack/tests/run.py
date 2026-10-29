"""Run deterministic local fixtures; zero selected tests is an error."""
import argparse
import json
import pathlib
import sys
import unittest
sys.dont_write_bytecode = True


class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.outcomes = []
    def addSuccess(self,test):
        super().addSuccess(test)
        self.outcomes.append({"test":test.id(),"status":"passed"})
    def addFailure(self,test,err):
        super().addFailure(test,err)
        self.outcomes.append({"test":test.id(),"status":"failed"})
    def addError(self,test,err):
        super().addError(test,err)
        self.outcomes.append({"test":test.id(),"status":"failed"})
    def addSkip(self,test,reason):
        super().addSkip(test,reason)
        self.outcomes.append({"test":test.id(),"status":"not-run","reason":reason})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern",default="test_*.py")
    parser.add_argument("--output")
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.discover(str(pathlib.Path(__file__).parent),pattern=args.pattern)
    count=suite.countTestCases()
    if count == 0:
        print(json.dumps({"status":"failed","reason":"zero tests collected","collected":0}))
        return 2
    result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    record={"kind":"deterministic unit/contract/synthetic integration tests",
            "qualification":"not a live model or host qualification",
            "collected":count,"executed":result.testsRun-len(result.skipped),
            "passed":sum(x["status"]=="passed" for x in result.outcomes),
            "failed":len(result.failures)+len(result.errors),"skipped":len(result.skipped),
            "status":"passed" if result.wasSuccessful() and not result.skipped else "failed",
            "tests":result.outcomes}
    if args.output:
        pathlib.Path(args.output).write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record,indent=2))
    return 0 if record["status"]=="passed" else 1


if __name__ == "__main__":
    sys.exit(main())

